import logging
import subprocess
import platform
import webbrowser
import shutil

class SystemController:
    def __init__(self):
        self.logger = logging.getLogger("SystemController")
        self.os_type = platform.system()
        self.logger.info(f"Инициализирован для ОС: {self.os_type}")
        
        # Определение доступного браузера
        self.browser = self._detect_browser()

    def _detect_browser(self):
        """Определение доступного браузера"""
        browsers = ["firefox", "chrome", "chromium", "microsoft-edge"]
        for browser in browsers:
            if shutil.which(browser):
                return browser
        return "firefox"  # Fallback

    def execute(self, command, raw_text=""):
        """Выполнение системной команды"""
        self.logger.info(f"Выполнение команды: {command}")
        
        try:
            if command == "open_browser":
                return self._open_url("about:blank")
            elif command == "open_youtube":
                return self._open_url("https://youtube.com")
            elif command == "open_google":
                return self._open_url("https://google.com")
            elif command == "new_tab":
                return self._open_url("about:blank")  # Упрощённая реализация
            elif command == "close_browser":
                return self._close_browser()
            elif command == "open_terminal":
                return self._open_terminal()
            elif command == "open_calculator":
                return self._open_calculator()
            else:
                return f"Команда '{command}' не реализована"
        except Exception as e:
            self.logger.error(f"Ошибка выполнения команды: {str(e)}")
            return "Ошибка выполнения команды"

    def _open_url(self, url):
        """Открытие URL в браузере по умолчанию"""
        self.logger.info(f"Открытие URL: {url}")
        
        try:
            webbrowser.open(url)
            return f"Открываю {url}"
        except Exception as e:
            self.logger.error(f"Ошибка открытия URL: {str(e)}")
            return "Не удалось открыть ссылку"

    def _close_browser(self):
        """Закрытие браузера"""
        self.logger.info(f"Закрытие браузера: {self.browser}")
        
        if self.os_type == "Windows":
            subprocess.Popen(["taskkill", "/f", "/im", f"{self.browser}.exe"])
        elif self.os_type == "Darwin":
            subprocess.Popen(["osascript", "-e", f'tell application "{self.browser}" to quit'])
        else:
            subprocess.Popen(["pkill", self.browser])
            
        return "Закрываю браузер"

    def _open_terminal(self):
        """Открытие терминала"""
        self.logger.info("Открытие терминала")
        
        if self.os_type == "Windows":
            subprocess.Popen(["start", "cmd"], shell=True)
        elif self.os_type == "Darwin":
            subprocess.Popen(["open", "-a", "Terminal"])
        else:
            # Популярные терминалы для Linux
            for term in ["gnome-terminal", "konsole", "xterm"]:
                if shutil.which(term):
                    subprocess.Popen([term])
                    return "Открываю терминал"
            return "Терминал не найден"
        
        return "Открываю терминал"

    def _open_calculator(self):
        """Открытие калькулятора"""
        self.logger.info("Открытие калькулятора")
        
        if self.os_type == "Windows":
            subprocess.Popen(["calc.exe"])
        elif self.os_type == "Darwin":
            subprocess.Popen(["open", "-a", "Calculator"])
        else:  # Linux
            # Попробуем разные калькуляторы
            calculators = ["gnome-calculator", "kcalc", "xcalc"]
            for calc in calculators:
                if shutil.which(calc):
                    subprocess.Popen([calc])
                    return "Открываю калькулятор"
            return "Калькулятор не найден"
