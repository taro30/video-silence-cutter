import logging
from PySide6.QtCore import QThread, Signal
from ..services.process_service import ProcessService
from ..models.silence_settings import SilenceSettings
from ..models.title_settings import TitleSettingsGroup
from ..models.output_settings import OutputSettings
from ..models.process_result import ProcessResult

logger = logging.getLogger(__name__)

class SilenceAnalysisWorker(QThread):
    progress_signal = Signal(float, str)
    finished_signal = Signal(object, object, object)  # (video_info, silence_list, keep_list)
    error_signal = Signal(str)

    def __init__(self, process_service: ProcessService, input_path: str, silence_settings: SilenceSettings):
        super().__init__()
        self.process_service = process_service
        self.input_path = input_path
        self.silence_settings = silence_settings

    def run(self):
        try:
            v_info, silences, keeps = self.process_service.analyze_silence_only(
                self.input_path,
                self.silence_settings,
                lambda pct, msg: self.progress_signal.emit(pct, msg)
            )
            self.finished_signal.emit(v_info, silences, keeps)
        except Exception as e:
            logger.error(f"Silence analysis failed: {e}", exc_info=True)
            self.error_signal.emit(str(e))


class VideoProcessWorker(QThread):
    progress_signal = Signal(float, str, float, float)  # pct, msg, elapsed, eta
    finished_signal = Signal(ProcessResult)
    error_signal = Signal(str)

    def __init__(
        self,
        process_service: ProcessService,
        input_path: str,
        output_path: str,
        silence_settings: SilenceSettings,
        title_settings: TitleSettingsGroup,
        output_settings: OutputSettings,
        cut_only: bool = False
    ):
        super().__init__()
        self.process_service = process_service
        self.input_path = input_path
        self.output_path = output_path
        self.silence_settings = silence_settings
        self.title_settings = title_settings
        self.output_settings = output_settings
        self.cut_only = cut_only

    def run(self):
        try:
            result = self.process_service.execute_full_pipeline(
                input_path=self.input_path,
                output_path=self.output_path,
                silence_settings=self.silence_settings,
                title_settings=self.title_settings,
                output_settings=self.output_settings,
                progress_cb=lambda pct, msg, el, eta: self.progress_signal.emit(pct, msg, el, eta),
                cut_only=self.cut_only
            )
            self.finished_signal.emit(result)
        except Exception as e:
            logger.error(f"Video process pipeline failed: {e}", exc_info=True)
            self.error_signal.emit(str(e))

    def cancel(self):
        self.process_service.cancel()
