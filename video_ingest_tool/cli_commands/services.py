"""
Services command for managing Prefect and API server lifecycle.

This module provides commands to start, stop, and check the status of
the video ingest tool services: Prefect server, Prefect worker, and API server.
"""

import os
import sys
import time
import signal
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import structlog
from . import BaseCommand

logger = structlog.get_logger(__name__)


class ServicesCommand(BaseCommand):
    """Command class for service management operations."""
    
    def __init__(self):
        self.prefect_port = int(os.environ.get('PREFECT_PORT', 4201))
        self.api_port = int(os.environ.get('API_PORT', 8001))
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Service process patterns for identification
        self.service_patterns = {
            'prefect-server': [
                'prefect server',
                'prefect.*server.*start'
            ],
            'prefect-worker': [
                'prefect worker.*video-processing-pool'
            ],
            'api-server': [
                'video_ingest_tool.api.server',
                'python.*video_ingest_tool.*api.*server',
                'api_server.py',
                'api_server_new.py'
            ]
        }
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute service management action.
        
        Args:
            action: One of 'start', 'stop', 'status', 'restart'
            service: Optional service name ('prefect-server', 'prefect-worker', 'api-server', 'all')
            port: Optional port override
            debug: Enable debug mode for API server
            foreground: Run API server in foreground
            
        Returns:
            Dict with success status and data/error
        """
        try:
            if action == 'start':
                return self._start_services(**kwargs)
            elif action == 'stop':
                return self._stop_services(**kwargs)
            elif action == 'status':
                return self._get_status(**kwargs)
            elif action == 'restart':
                return self._restart_services(**kwargs)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"Service command failed", action=action, error=str(e))
            return {"success": False, "error": str(e)}
    
    def _find_available_port(self, preferred_port: int) -> int:
        """Find an available port starting from preferred port."""
        port = preferred_port
        while port < preferred_port + 100:  # Try 100 ports
            if not self._is_port_in_use(port):
                return port
            port += 1
        raise RuntimeError(f"No available ports found starting from {preferred_port}")
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        try:
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True)
            return result.returncode == 0 and result.stdout.strip()
        except:
            return False
    
    def _get_processes_on_port(self, port: int) -> List[Tuple[int, str]]:
        """Get list of (PID, command) using a port."""
        try:
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return []
            
            processes = []
            for pid_str in result.stdout.strip().split('\n'):
                if pid_str:
                    try:
                        pid = int(pid_str)
                        # Get process command using ps
                        ps_result = subprocess.run(['ps', '-p', str(pid), '-o', 'args='], 
                                                 capture_output=True, text=True)
                        if ps_result.returncode == 0:
                            cmd = ps_result.stdout.strip()
                            processes.append((pid, cmd))
                    except (ValueError, subprocess.SubprocessError):
                        continue
            return processes
        except:
            return []
    
    def _process_exists(self, pid: int) -> bool:
        """Check if a process exists."""
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def _clear_port(self, port: int, service_name: str) -> bool:
        """Clear a port of our processes, return True if cleared successfully."""
        processes = self._get_processes_on_port(port)
        if not processes:
            return True
        
        patterns = self.service_patterns.get(service_name, [])
        cleared_any = False
        
        for pid, cmd in processes:
            is_ours = any(pattern in cmd for pattern in patterns)
            
            if is_ours:
                logger.info(f"Killing our {service_name} process", pid=pid, cmd=cmd)
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                    if self._process_exists(pid):
                        os.kill(pid, signal.SIGKILL)
                    cleared_any = True
                except ProcessLookupError:
                    pass
            else:
                logger.warning(f"Port {port} used by unrelated process", pid=pid, cmd=cmd)
                return False
        
        return cleared_any
    
    def _kill_service_processes(self, service_name: str):
        """Kill all processes matching service patterns."""
        patterns = self.service_patterns.get(service_name, [])
        if not patterns:
            return
        
        for pattern in patterns:
            try:
                result = subprocess.run(['pgrep', '-f', pattern], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    for pid_str in result.stdout.strip().split('\n'):
                        if pid_str:
                            try:
                                pid = int(pid_str)
                                logger.info(f"Killing {service_name} process", pid=pid)
                                os.kill(pid, signal.SIGTERM)
                                time.sleep(0.5)
                                if self._process_exists(pid):
                                    os.kill(pid, signal.SIGKILL)
                            except (ValueError, ProcessLookupError):
                                pass
            except:
                pass
    
    def _wait_for_health(self, url: str, timeout: int = 60) -> bool:
        """Wait for a service health endpoint to respond."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(2)
        return False
    
    def _setup_prefect_env(self, port: int):
        """Set up Prefect environment variables."""
        os.environ['PREFECT_API_DATABASE_CONNECTION_URL'] = 'sqlite+aiosqlite:///./data/prefect.db'
        os.environ['PREFECT_API_URL'] = f'http://127.0.0.1:{port}/api'
    
    def _create_concurrency_limits(self):
        """Create Prefect concurrency limits."""
        limits = [
            ('video_compression_step', 2),
            ('ai_analysis_step', 1),
            ('transcription_step', 2),
            ('embedding_step', 2)
        ]
        
        for name, limit in limits:
            try:
                result = subprocess.run([
                    'prefect', 'concurrency-limit', 'create', name, str(limit)
                ], capture_output=True, text=True)
                if result.returncode != 0 and 'already exists' not in result.stderr:
                    logger.warning(f"Failed to create concurrency limit {name}", error=result.stderr)
            except Exception as e:
                logger.warning(f"Failed to create concurrency limit {name}", error=str(e))
    
    def _start_prefect_server(self, port: int) -> Dict[str, Any]:
        """Start Prefect server."""
        # Clear existing processes
        if not self._clear_port(port, 'prefect-server'):
            return {"success": False, "error": f"Port {port} is in use by another process"}
        
        # Set up environment
        self._setup_prefect_env(port)
        
        # Start server
        log_file = self.logs_dir / "prefect_server.log"
        try:
            with open(log_file, 'w') as f:
                process = subprocess.Popen([
                    'prefect', 'server', 'start', '--port', str(port)
                ], stdout=f, stderr=subprocess.STDOUT)
            
            # Wait for health check
            health_url = f"http://127.0.0.1:{port}/api/health"
            if not self._wait_for_health(health_url, timeout=60):
                return {"success": False, "error": "Prefect server failed to start within timeout"}
            
            # Create concurrency limits
            self._create_concurrency_limits()
            
            return {
                "success": True, 
                "data": {
                    "service": "prefect-server",
                    "pid": process.pid,
                    "port": port,
                    "log_file": str(log_file)
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to start Prefect server: {str(e)}"}
    
    def _start_prefect_worker(self) -> Dict[str, Any]:
        """Start Prefect worker."""
        # Kill existing workers
        self._kill_service_processes('prefect-worker')
        
        log_file = self.logs_dir / "prefect_worker.log"
        try:
            with open(log_file, 'w') as f:
                process = subprocess.Popen([
                    'prefect', 'worker', 'start', 
                    '--pool', 'video-processing-pool',
                    '--type', 'process'
                ], stdout=f, stderr=subprocess.STDOUT)
            
            # Give it a moment to start
            time.sleep(2)
            
            return {
                "success": True,
                "data": {
                    "service": "prefect-worker", 
                    "pid": process.pid,
                    "log_file": str(log_file)
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to start Prefect worker: {str(e)}"}
    
    def _start_api_server(self, port: int, debug: bool = False, foreground: bool = False) -> Dict[str, Any]:
        """Start API server."""
        # Clear existing processes
        if not self._clear_port(port, 'api-server'):
            return {"success": False, "error": f"Port {port} is in use by another process"}
        
        log_file = self.logs_dir / "api_server.log"
        cmd = ['python', '-m', 'video_ingest_tool.api.server', '--port', str(port)]
        if debug:
            cmd.append('--debug')
        
        try:
            if foreground:
                # Run in foreground with live output
                process = subprocess.Popen(cmd)
                return {
                    "success": True,
                    "data": {
                        "service": "api-server",
                        "pid": process.pid,
                        "port": port,
                        "foreground": True,
                        "message": "API server running in foreground. Press Ctrl+C to stop."
                    }
                }
            else:
                # Run in background
                with open(log_file, 'w') as f:
                    process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
                
                # Wait for health check
                health_url = f"http://127.0.0.1:{port}/api/health"
                if not self._wait_for_health(health_url, timeout=30):
                    return {"success": False, "error": "API server failed to start within timeout"}
                
                return {
                    "success": True,
                    "data": {
                        "service": "api-server",
                        "pid": process.pid,
                        "port": port,
                        "log_file": str(log_file)
                    }
                }
        except Exception as e:
            return {"success": False, "error": f"Failed to start API server: {str(e)}"}
    
    def _write_port_config(self, prefect_port: int, api_port: int):
        """Write port configuration to files for front-end consumption."""
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        
        # Write to JSON for programmatic access
        config_file = config_dir / "ports.json"
        port_config = {
            "prefect_port": prefect_port,
            "api_port": api_port,
            "prefect_url": f"http://127.0.0.1:{prefect_port}/api",
            "api_url": f"http://localhost:{api_port}/api"
        }
        
        with open(config_file, 'w') as f:
            import json
            json.dump(port_config, f, indent=2)
        
        # Write shell export statements for manual sourcing
        env_file = config_dir / "ports.env"
        with open(env_file, 'w') as f:
            f.write(f"export PREFECT_PORT={prefect_port}\n")
            f.write(f"export API_PORT={api_port}\n")
            f.write(f"export PREFECT_API_URL=http://127.0.0.1:{prefect_port}/api\n")
            f.write(f"export API_BASE_URL=http://localhost:{api_port}/api\n")
        
        logger.info(f"Port configuration written to {config_file} and {env_file}")
    
    def _start_services(self, service: str = 'all', port: Optional[int] = None, 
                       debug: bool = False, foreground: bool = False) -> Dict[str, Any]:
        """Start one or more services."""
        results = []
        
        # Determine ports
        prefect_port = port if service == 'prefect-server' and port else self._find_available_port(self.prefect_port)
        api_port = port if service == 'api-server' and port else self._find_available_port(self.api_port)
        
        # Write port configuration for front-end consumption
        self._write_port_config(prefect_port, api_port)
        
        if service in ['prefect-server', 'all']:
            result = self._start_prefect_server(prefect_port)
            results.append(result)
            if not result['success'] and service == 'prefect-server':
                return result
        
        if service in ['prefect-worker', 'all']:
            result = self._start_prefect_worker()
            results.append(result)
            if not result['success'] and service == 'prefect-worker':
                return result
        
        if service in ['api-server', 'all']:
            result = self._start_api_server(api_port, debug, foreground)
            results.append(result)
            if not result['success'] and service == 'api-server':
                return result
        
        # Return combined results with port info
        all_success = all(r['success'] for r in results)
        return {
            "success": all_success,
            "data": {
                "services": [r['data'] for r in results if r['success']],
                "ports": {
                    "prefect_port": prefect_port,
                    "api_port": api_port
                },
                "config_files": {
                    "json": "config/ports.json",
                    "env": "config/ports.env"
                },
                "message": f"Started {len([r for r in results if r['success']])} service(s)"
            }
        }
    
    def _stop_services(self, service: str = 'all') -> Dict[str, Any]:
        """Stop one or more services."""
        stopped = []
        
        services_to_stop = []
        if service == 'all':
            services_to_stop = ['api-server', 'prefect-worker', 'prefect-server']
        else:
            services_to_stop = [service]
        
        for svc in services_to_stop:
            try:
                if svc == 'api-server':
                    self._clear_port(self.api_port, 'api-server')
                    self._kill_service_processes('api-server')
                elif svc == 'prefect-worker':
                    self._kill_service_processes('prefect-worker')
                elif svc == 'prefect-server':
                    self._clear_port(self.prefect_port, 'prefect-server')
                    self._kill_service_processes('prefect-server')
                
                stopped.append(svc)
            except Exception as e:
                logger.warning(f"Error stopping {svc}", error=str(e))
        
        return {
            "success": True,
            "data": {
                "stopped_services": stopped,
                "message": f"Stopped {len(stopped)} service(s)"
            }
        }
    
    def _get_status(self) -> Dict[str, Any]:
        """Get status of all services."""
        status = {}
        
        # Check Prefect server
        prefect_processes = self._get_processes_on_port(self.prefect_port)
        status['prefect-server'] = {
            "running": len(prefect_processes) > 0,
            "port": self.prefect_port,
            "processes": prefect_processes
        }
        
        # Check API server  
        api_processes = self._get_processes_on_port(self.api_port)
        status['api-server'] = {
            "running": len(api_processes) > 0,
            "port": self.api_port,
            "processes": api_processes
        }
        
        # Check Prefect worker (no specific port)
        worker_running = False
        try:
            result = subprocess.run(['pgrep', '-f', 'prefect worker.*video-processing-pool'], 
                                  capture_output=True, text=True)
            worker_running = result.returncode == 0 and result.stdout.strip()
        except:
            pass
        
        status['prefect-worker'] = {
            "running": worker_running
        }
        
        return {
            "success": True,
            "data": {"services": status}
        }
    
    def _restart_services(self, service: str = 'all', **kwargs) -> Dict[str, Any]:
        """Restart one or more services."""
        # Stop first
        stop_result = self._stop_services(service)
        if not stop_result['success']:
            return stop_result
        
        # Wait a moment
        time.sleep(2)
        
        # Start again
        return self._start_services(service, **kwargs) 