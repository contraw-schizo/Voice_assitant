import os
import time
import queue
import threading
import numpy as np
import sounddevice as sd
import pvporcupine
from vosk import Model, KaldiRecognizer
import torch
import json
import logging
from silero import silero_tts

class VoiceEngine:
    def __init__(self, picovoice_token, mic_index=None, sample_rate=16000):
        # Конфигурация
        self.picovoice_token = picovoice_token
        self.sample_rate = sample_rate
        self.mic_index = mic_index
        self.frame_length = 512
        
        # Состояние
        self.is_active = False
        
        # Ресурсы
        self.porcupine = None
        self.vosk_model = None
        self.recorder = None
        self.audio_queue = queue.Queue()
        self.tts_model = None
        
        # Логгер
        self.logger = logging.getLogger("VoiceEngine")

    def load_models(self):
        """Загрузка необходимых моделей"""
        try:
            # Инициализация Porcupine
            if not self.porcupine:
                self.porcupine = pvporcupine.create(
                    access_key=self.picovoice_token,
                    keywords=['jarvis'],
                    sensitivities=[0.7]
                )
                self.logger.info("Porcupine инициализирован")
            
            # Инициализация Vosk
            if not self.vosk_model:
                # Проверка существования пути к модели
                model_path = "models/vosk"
                if not os.path.exists(model_path):
                    self.logger.error(f"Путь к модели Vosk не существует: {model_path}")
                    raise FileNotFoundError(f"Модель Vosk не найдена по пути: {model_path}")
                
                self.vosk_model = Model(model_path)
                self.logger.info("Vosk модель загружена")
            
            # Инициализация TTS
            if not self.tts_model:
                tts_result = silero_tts(language='ru',
                                        speaker='ru_v3',
                                        device=torch.device('cpu'))
            # Сохраняем только модель
                self.tts_model = tts_result[0]
                self.logger.info("TTS модель загружена")
                
        except pvporcupine.PorcupineInvalidArgumentError:
            self.logger.error("Неверный Picovoice токен")
            raise
        except Exception as e:
            self.logger.error(f"Ошибка загрузки моделей: {str(e)}")
            raise RuntimeError(f"Ошибка инициализации голосового движка: {str(e)}")

    def unload_models(self):
        """Выгрузка моделей и освобождение ресурсов"""
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
            self.logger.debug("Porcupine выгружен")
        
        self.vosk_model = None
        self.tts_model = None
        self.logger.debug("Модели выгружены")

    def set_mic_state(self, enabled):
        """Включение/выключение микрофона"""
        if enabled and not self.is_active:
            self._start_listening()
        elif not enabled and self.is_active:
            self._stop_listening()

    def _start_listening(self):
        """Запуск прослушивания микрофона"""
        try:
            self.load_models()
            device_info = "default" if self.mic_index is None else f"device {self.mic_index}"
            self.logger.info(f"Запуск микрофона ({device_info}), sample_rate={self.sample_rate}, frame_length={self.frame_length}")
            self.recorder = sd.InputStream(
                device=self.mic_index,
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.frame_length,
                callback=self._audio_callback
            )
            self.recorder.start()
            self.is_active = True
            self.logger.info("Микрофон активирован")
        except Exception as e:
            self.logger.error(f"Ошибка запуска микрофона: {str(e)}")
            self.unload_models()
            raise

    def _stop_listening(self):
        """Остановка прослушивания микрофона"""
        if not self.is_active:
            return
            
        try:
            if self.recorder:
                self.recorder.stop()
                self.recorder.close()
                self.recorder = None
                
            self.is_active = False
            self.logger.info("Микрофон деактивирован")
        except Exception as e:
            self.logger.error(f"Ошибка остановки микрофона: {str(e)}")
            raise

    def _audio_callback(self, indata, frames, time, status):
        """Callback для обработки аудиопотока"""
        if status:
            self.logger.warning(f"Аудио статус: {status}")
        
        # Конвертация в моно при необходимости (НЕ ИСПОЛЬЗУЕТСЯ)
        if indata.ndim > 1:
            indata = indata[:, 0]
            # indata = np.mean(indata, axis=1)
            
        self.audio_queue.put(indata.copy())

    def check_activation(self):
        """Проверка наличия wake-word"""
        if not self.is_active:
            return False
            
        try:
            audio_frame = self.audio_queue.get_nowait()
            keyword_index = self.porcupine.process(audio_frame.flatten())
            return keyword_index >= 0
        except queue.Empty:
            return False
        except Exception as e:
            self.logger.error(f"Ошибка проверки активации: {str(e)}")
            return False

    def record_command(self, duration=2):
        """Запись и распознавание команды"""
        if not self.is_active:
            self.logger.warning("Попытка записи при неактивном микрофоне")
            return ""
        self.logger.info(f"Начало записи команды ({duration} сек)")    
        audio_frames = []
        start_time = time.time()
        
        # Сбор аудио данных
        while time.time() - start_time < duration:
            try:
                audio_frames.append(self.audio_queue.get_nowait())
            except queue.Empty:
                time.sleep(0.01)
                
        if not audio_frames:
            return ""
        
        total_samples = sum(frame.shape[0] for frame in audio_frames)
        self.logger.debug(f"Запись завершена: {len(audio_frames)} фреймов, {total_samples} сэмплов")    
        # Объединение фреймов
        audio_data = np.concatenate(audio_frames)
        
        # Распознавание команды
        try:
            recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
            recognizer.AcceptWaveform(audio_data.tobytes())
            result = json.loads(recognizer.Result())
            return result.get("text", "").strip()
        except Exception as e:
            self.logger.error(f"Ошибка распознавания: {str(e)}")
            return ""

    def speak(self, text, output_device=None):
        """Синтез и воспроизведение речи с защитой от самоперехвата"""
        if not text or not self.tts_model:
            return
            
        was_active = self.is_active
        try:
            # Временное отключение микрофона
            if was_active:
                self._stop_listening()
            
            # Генерация и воспроизведение речи
            audio = self.tts_model.apply_tts(
                text=text,
                speaker='aidar',  # Идентификатор голоса
                sample_rate=48000,
                put_accent=True,
                put_yo=True
            )
            
            sd.play(audio, samplerate=48000, device=output_device)
            sd.wait()
        except Exception as e:
            self.logger.error(f"Ошибка синтеза речи: {str(e)}")
        finally:
            # Восстановление состояния микрофона
            if was_active:
                self._start_listening()

    def cleanup(self):
        """Полное освобождение ресурсов"""
        self._stop_listening()
        self.unload_models()
        self.logger.info("Ресурсы голосового движка освобождены")
