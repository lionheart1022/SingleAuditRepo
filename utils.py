import os
import ssl
import sys
import time
import urllib.request
from ftplib import FTP, error_perm
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select


class Crawler:
    def __init__(self, config, section):
        self.section = section
        self.downloads_path = config.get(section, 'downloads_path', fallback='/tmp/downloads/')
        if not os.path.exists(self.downloads_path):
            os.makedirs(self.downloads_path)
        elif not os.path.isdir(self.downloads_path):
            print('ERROR:{} downloads_path parameter points to file!'.format(section))
            sys.exit(1)
        if config.getboolean('general', 'headless_mode', fallback=False):
            display = Display(visible=0, size=(1920, 1080))
            display.start()
        self.config = config
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        prefs = {
            'download.default_directory': self.downloads_path,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'plugins.always_open_pdf_externally': True,
        }
        options.add_experimental_option("prefs", prefs)
        self.browser = webdriver.Chrome(chrome_options=options, service_args=["--verbose", "--log-path=/tmp/selenium.log"])
        self.browser.implicitly_wait(10)

        self.ftp = FTP()
        self.ftp.connect(
            self.config.get('general', 'ftp_server').strip(),
            int(self.config.get('general', 'ftp_port')),
        )
        self.ftp.login(
            user=self.config.get('general', 'ftp_username').strip(),
            passwd=self.config.get('general', 'ftp_password').strip(),
        )
        print('Connection to ftp successfully established...')

    def get(self, url):
        self.browser.get(url)
        time.sleep(3)

    def assert_exists(self, selector):
        _ = self.browser.find_element_by_css_selector(selector)

    def get_elements(self, selector, root=None):
        if root is None:
            root = self.browser
        return root.find_elements_by_css_selector(selector)

    def wait_for_displayed(self, selector):
        element = self.browser.find_element_by_css_selector(selector)
        while not element.is_displayed():
            pass

    def click_by_text(self, text):
        self.browser.find_element_by_link_text(text)
        time.sleep(3)

    def click_xpath(self, path, single=True):
        if single:
            self.browser.find_element_by_xpath(path).click()
        else:
            for el in self.browser.find_elements_by_xpath(path):
                el.click()
        time.sleep(3)

    def click(self, selector, single=True, root=None):
        if root is None:
            root = self.browser
        if single:
            root.find_element_by_css_selector(selector).click()
        else:
            for el in root.find_elements_by_css_selector(selector):
                el.click()
        time.sleep(3)

    def send_keys(self, selector, keys):
        elem = self.browser.find_element_by_css_selector(selector)
        elem.clear()
        elem.send_keys(keys)
        time.sleep(3)

    def open_new_tab(self):
        self.browser.execute_script("window.open('');")
        self.browser.switch_to.window(self.browser.window_handles[1])

    def close_current_tab(self):
        self.browser.close()
        self.browser.switch_to.window(self.browser.window_handles[-1])

    def get_text(self, selector, single=True, root=None):
        if root is None:
            root = self.browser
        if single:
            return root.find_element_by_css_selector(selector).text
        return [el.text for el in root.find_elements_by_css_selector(selector)]

    def get_attr(self, selector, attr, single=True, root=None):
        if root is None:
            root = self.browser
        if single:
            return root.find_element_by_css_selector(selector).get_attribute(attr)
        return [el.get_attribute(attr) for el in root.find_elements_by_css_selector(selector)]

    def execute(self, script):
        self.browser.execute_script(script, [])
        time.sleep(3)

    def deselect_all(self, selector):
        select = Select(self.browser.find_element_by_css_selector(selector))
        select.deselect_all()
        time.sleep(3)

    def select_option(self, selector, option):
        select = Select(self.browser.find_element_by_css_selector(selector))
        select.select_by_visible_text(option)
        time.sleep(3)

    def select_option_by_index(self, selector, index):
        select = Select(self.browser.find_element_by_css_selector(selector))
        if index < len(select.options):
            select.select_by_index(index)
            time.sleep(3)
            return True
        return False

    def back(self):
        self.browser.back()
        time.sleep(3)

    def close(self):
        self.browser.quit()
        self.ftp.quit()

    def download(self, url, filename):
        print('Downloading', filename, self._get_remote_filename(filename))
        # return
        if url.startswith('https'):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx = None
        try:
            r = urllib.request.urlopen(url, context=ctx)
            with open(os.path.join(self.downloads_path, filename), 'wb') as f:
                f.write(r.read())
        except Exception:
            print('ERROR: Downloading failed!')

    def _get_remote_filename(self, local_filename):
        raise NotImplemented

    def merge_files(self, filenames):
        pdfline = ' '.join(filenames)
        res_filename = filenames[0].split(' part')[0] + '.pdf'
        command = 'pdftk ' + pdfline + ' cat output ' + res_filename
        os.system(command)
        return res_filename

    def upload_to_ftp(self, filename):
        try:
            path = os.path.join(self.downloads_path, filename)
            print('Uploading {}'.format(path))
            pdf_file = open(path, 'rb')
            remote_filename = self._get_remote_filename(filename)
            if not remote_filename:
                return
            directory, filename = remote_filename
            self.ftp.cwd('/{}'.format(directory))
            # if not self.config.getboolean(self.section, 'overwrite_remote_files', fallback=False):
            #     print('Checking if {}/{} already exists'.format(directory, filename))
            #     try:
            #         self.ftp.retrbinary('RETR {}'.format(filename), lambda x: x)
            #         return
            #     except error_perm:
            #         pass

            self.ftp.storbinary('STOR {}'.format(filename), pdf_file)
            print('{} uploaded'.format(path))
            pdf_file.close()
        except Exception as e:
            print(str(e))
