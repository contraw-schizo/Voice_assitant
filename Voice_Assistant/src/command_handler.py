import logging
import yaml
from fuzzywuzzy import fuzz
from src.system_controller import SystemController

class CommandHandler:
    def __init__(self):
        self.logger = logging.getLogger("CommandHandler")
        self.system_controller = SystemController()
        self.commands = self._load_commands()
        self.threshold = 70
        self.assistant_aliases = ["джарвис", "jarvis", "ассистент", "помощник"]  # Дополненный список

    def _load_commands(self):
        try:
            with open('commands.yaml', 'rt', encoding='utf-8') as f:
                commands = yaml.safe_load(f)
                self.logger.info(f"Загружено {len(commands)} команд")
                return commands
        except FileNotFoundError:
            self.logger.error("Файл commands.yaml не найден!")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Ошибка разбора YAML: {str(e)}")
            return {}
        except Exception as e:
            self.logger.error(f"Ошибка загрузки команд: {str(e)}")
            return {}

    def _remove_assistant_alias(self, text):
        """Удаление обращения к ассистенту в начале фразы"""
        lower_text = text.lower()
        for alias in self.assistant_aliases:
            # Проверяем, начинается ли текст с обращения + пробела/запятой
            if lower_text.startswith(alias + " ") or lower_text.startswith(alias + ","):
                return text[len(alias):].lstrip(" ,").strip()
        return text

    def _recognize_command(self, text):
        """Поиск команды с улучшенной обработкой обращений"""
        # Очищаем от обращения и лишних пробелов
        clean_text = self._remove_assistant_alias(text)
        clean_text_lower = clean_text.lower()
        
        best_cmd = None
        best_score = 0
        
        # Поиск наилучшего совпадения
        for cmd, aliases in self.commands.items():
            for alias in aliases:
                score = fuzz.ratio(clean_text_lower, alias.lower())
                if score > best_score:
                    best_score = score
                    best_cmd = cmd
        
        self.logger.debug(f"Распознано: '{text}' -> '{clean_text}' -> {best_cmd} ({best_score}%)")
        return best_cmd, best_score

    def handle(self, text, input_type="voice"):
        self.logger.info(f"Обработка команды ({input_type}): '{text}'")
        
        command, score = self._recognize_command(text)
        
        if command and score >= self.threshold:
            try:
                response = self.system_controller.execute(command, text)
                self.logger.info(f"Выполнена команда: {command}")
                return response
            except Exception as e:
                error_msg = f"Ошибка выполнения: {str(e)}"
                self.logger.error(error_msg)
                return error_msg
        
        return self._handle_with_llm(text)

    def _handle_with_llm(self, text):
        # Заглушка
        self.logger.info(f"Передача в LLM: '{text}'")
        return "Я пока не умею отвечать на общие вопросы, но скоро научусь!"
