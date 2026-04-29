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

async def run_command_with_heartbeat(cmd, step_name, retries=3, delay=2, backoff=2, timeout=120):
    """
    Runs a subprocess and yields heartbeats to keep the connection alive.
    Returns True on success, raises exception on final failure.
    """
    _delay = delay
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"[{step_name}] Attempt {attempt}/{retries} (Timeout: {timeout}s)")
            
            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait for completion with heartbeat
            start_time = time.time()
            while process.returncode is None:
                try:
                    # Wait for 5 seconds for completion
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Yield heartbeat to keep connection alive
                    yield {"type": "heartbeat", "content": f"{step_name} in progress..."}
                    
                    # Check overall timeout
                    if time.time() - start_time > timeout:
                        process.kill()
                        raise subprocess.TimeoutExpired(cmd, timeout)

            if process.returncode != 0:
                stdout, stderr = await process.communicate()
                raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
            
            # Success!
            return

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"[{step_name}] Attempt {attempt} failed: {getattr(e, 'stderr', str(e))}")
            if attempt == retries:
                raise
            await asyncio.sleep(_delay)
            _delay *= backoff
