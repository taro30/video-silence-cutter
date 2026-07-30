import os
import signal
import subprocess
import time
import logging

logger = logging.getLogger(__name__)

def kill_process_group(process: subprocess.Popen, timeout: float = 2.0) -> None:
    if process.poll() is not None:
        return

    pid = process.pid
    try:
        pgid = os.getpgid(pid)
        logger.info(f"Sending SIGTERM to process group {pgid}")
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception as e:
        logger.warning(f"Failed to send SIGTERM to process group: {e}")
        try:
            process.terminate()
        except Exception:
            pass

    start_time = time.time()
    while time.time() - start_time < timeout:
        if process.poll() is not None:
            logger.info("Process terminated gracefully.")
            return
        time.sleep(0.1)

    try:
        pgid = os.getpgid(pid)
        logger.warning(f"Process did not terminate in {timeout}s. Sending SIGKILL to process group {pgid}")
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception as e:
        logger.error(f"Failed to send SIGKILL to process group: {e}")
        try:
            process.kill()
        except Exception:
            pass
