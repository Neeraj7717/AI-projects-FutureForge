import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

import threading
import logging
from typing import Optional
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations

logger = LoggerOperations(logger_name='model_manager', log_level=logging.INFO, use_log_file=False)

class ModelManager:
    """
    Global singleton for managing ML models.
    Shared between API and Consumer to avoid duplicate loading.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized'):
            return

        # Model instances
        self._pose_obj = None
        self._detector = None
        self._gender = None

        # Model ready flags
        self._pose_ready = threading.Event()
        self._detector_ready = threading.Event()
        self._gender_ready = threading.Event()

        # Model loading locks
        self._pose_loading = threading.Lock()
        self._detector_loading = threading.Lock()
        self._gender_loading = threading.Lock()

        # Config
        from Config.settings import Settings
        self.config = Settings()

        self._initialized = True
        logger.info("ModelManager initialized")

    def load_all_models(self):
        """
        Pre-load all models at startup.
        Call this when load_all_models_at_start=True
        """
        logger.info("Loading all models at startup...")

        # Load all 3 models
        self.get_pose_model()
        self.get_detector_model()
        self.get_gender_model()

        logger.info("✓✓✓ All models loaded successfully!")

    def get_pose_model(self) -> Optional[object]:
        """
        Get Pose model instance.
        Loads on first call if not already loaded (lazy loading).
        """
        # If model is ready, return it
        if self._pose_ready.is_set():
            return self._pose_obj

        # Try to acquire lock - only one thread loads the model
        if not self._pose_loading.acquire(blocking=False):
            # Another thread is loading, skip or wait
            logger.info("Pose model is loading by another thread, skipping...")
            return None

        try:
            # Double-check in case another thread finished while we waited
            if self._pose_ready.is_set():
                return self._pose_obj

            logger.info("Loading Pose model...")
            from model.pose_model import Pose
            self._pose_obj = Pose()
            self._pose_ready.set()
            logger.info("✓ Pose model loaded and ready!")
            return self._pose_obj

        except Exception as e:
            logger.error(f"Error loading Pose model: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self._pose_loading.release()

    def get_detector_model(self) -> Optional[object]:
        """
        Get Detections model instance.
        Loads on first call if not already loaded (lazy loading).
        """
        # If model is ready, return it
        if self._detector_ready.is_set():
            return self._detector

        # Try to acquire lock - only one thread loads the model
        if not self._detector_loading.acquire(blocking=False):
            # Another thread is loading, skip or wait
            logger.info("Detector model is loading by another thread, skipping...")
            return None

        try:
            # Double-check in case another thread finished while we waited
            if self._detector_ready.is_set():
                return self._detector

            logger.info("Loading Detections model...")
            from model.detections import Detections
            self._detector = Detections()
            self._detector_ready.set()
            logger.info("✓ Detections model loaded and ready!")
            return self._detector

        except Exception as e:
            logger.error(f"Error loading Detections model: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self._detector_loading.release()

    def get_gender_model(self) -> Optional[object]:
        """
        Get Gender/ProcessFrame model instance.
        Loads on first call if not already loaded (lazy loading).
        """
        # If model is ready, return it
        if self._gender_ready.is_set():
            return self._gender

        # Try to acquire lock - only one thread loads the model
        if not self._gender_loading.acquire(blocking=False):
            # Another thread is loading, skip or wait
            logger.info("Gender model is loading by another thread, skipping...")
            return None

        try:
            # Double-check in case another thread finished while we waited
            if self._gender_ready.is_set():
                return self._gender

            logger.info("Loading Gender/ProcessFrame model...")
            from model.gender_model import ProcessFrame
            self._gender = ProcessFrame()
            self._gender_ready.set()
            logger.info("✓ Gender model loaded and ready!")
            return self._gender

        except Exception as e:
            logger.error(f"Error loading Gender model: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self._gender_loading.release()

    def is_pose_ready(self) -> bool:
        """Check if Pose model is loaded and ready"""
        return self._pose_ready.is_set()

    def is_detector_ready(self) -> bool:
        """Check if Detector model is loaded and ready"""
        return self._detector_ready.is_set()

    def is_gender_ready(self) -> bool:
        """Check if Gender model is loaded and ready"""
        return self._gender_ready.is_set()

    def close(self):
        """Clean up model resources"""
        logger.info("Closing models...")
        if self._pose_obj and hasattr(self._pose_obj, 'close'):
            self._pose_obj.close()
        logger.info("✓ Models closed")


# Global singleton instance
model_manager = ModelManager()
