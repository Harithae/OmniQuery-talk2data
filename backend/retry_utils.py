import time
import logging
import subprocess
import asyncio
import sys
from functools import wraps

logger = logging.getLogger(__name__)

def retry_decorator(retries=3, delay=2, backoff=2, exceptions=(Exception,), timeout=None):
    """
    Decorator for retrying a function with exponential backoff.
    Works for both sync and async functions.
    'timeout' can be used if the underlying function supports it.
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                _delay = delay
                if timeout: kwargs['timeout'] = timeout
                for attempt in range(1, retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == retries:
                            logger.error(f"Async attempt {attempt} failed for {func.__name__}: {e}")
                            raise
                        logger.warning(f"Async attempt {attempt} failed for {func.__name__}. Retrying in {_delay}s... Error: {e}")
                        await asyncio.sleep(_delay)
                        _delay *= backoff
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                _delay = delay
                if timeout: kwargs['timeout'] = timeout
                for attempt in range(1, retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == retries:
                            logger.error(f"Sync attempt {attempt} failed for {func.__name__}: {e}")
                            raise
                        logger.warning(f"Sync attempt {attempt} failed for {func.__name__}. Retrying in {_delay}s... Error: {e}")
                        time.sleep(_delay)
                        _delay *= backoff
            return sync_wrapper
    return decorator

async def run_command_with_retry(cmd, step_name, retries=3, delay=2, backoff=2, timeout=120):
    """
    Runs a subprocess command with retry logic, exponential backoff, and an explicit timeout.
    """
    _delay = delay
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"[{step_name}] Attempt {attempt}/{retries} (Timeout: {timeout}s)")
            # Passing timeout to subprocess.run
            process = await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True, text=True, timeout=timeout)
            return process
        except subprocess.TimeoutExpired as e:
            logger.error(f"[{step_name}] Attempt {attempt} timed out after {timeout}s")
            if attempt == retries:
                raise
            await asyncio.sleep(_delay)
            _delay *= backoff
        except subprocess.CalledProcessError as e:
            logger.error(f"[{step_name}] Attempt {attempt} failed: {e.stderr}")
            if attempt == retries:
                raise
            logger.warning(f"Retrying {step_name} in {_delay}s...")
            await asyncio.sleep(_delay)
            _delay *= backoff
