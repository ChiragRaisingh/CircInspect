# Copyright 2026 UBC Quantum Software and Algorithms Research Lab

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest.mock import patch, call
from server import container_manager

class StopLoopException(Exception):
    pass

def test_reaper_loop_no_expired_sessions():
    """
    Test that the reaper loop does not call stop_container when all sessions
    have been active recently enough and are not expired.
    """
    with patch("server.container_manager.time.sleep") as mock_sleep, \
         patch("server.container_manager.time.time") as mock_time, \
         patch("server.container_manager.stop_container") as mock_stop_container, \
         patch.dict("server.container_manager._session_last_active", {"session1": 1000, "session2": 2000}, clear=True):
        
        mock_sleep.side_effect = [None, StopLoopException]
        mock_time.return_value = 2500
        
        try:
            container_manager._reaper_loop()
        except StopLoopException:
            pass
            
        assert mock_sleep.call_count == 2
        mock_stop_container.assert_not_called()

def test_reaper_loop_with_expired_sessions():
    """
    Test that the reaper loop calls stop_container for a single session
    that has exceeded the inactivity timeout, while leaving others alone.
    """
    with patch("server.container_manager.time.sleep") as mock_sleep, \
         patch("server.container_manager.time.time") as mock_time, \
         patch("server.container_manager.stop_container") as mock_stop_container, \
         patch.dict("server.container_manager._session_last_active", {"session1": 1000, "session2": 2000, "session3": 3000}, clear=True):
        
        mock_sleep.side_effect = [None, StopLoopException]
        mock_time.return_value = 5000
        
        try:
            container_manager._reaper_loop()
        except StopLoopException:
            pass
            
        assert mock_sleep.call_count == 2
        mock_stop_container.assert_called_once_with("session1")

def test_reaper_loop_multiple_expired_sessions():
    """
    Test that the reaper loop calls stop_container for all sessions
    that have exceeded the inactivity timeout.
    """
    with patch("server.container_manager.time.sleep") as mock_sleep, \
         patch("server.container_manager.time.time") as mock_time, \
         patch("server.container_manager.stop_container") as mock_stop_container, \
         patch.dict("server.container_manager._session_last_active", {"session1": 1000, "session2": 2000, "session3": 5000}, clear=True):
        
        mock_sleep.side_effect = [None, StopLoopException]
        mock_time.return_value = 6000
        
        try:
            container_manager._reaper_loop()
        except StopLoopException:
            pass
            
        assert mock_sleep.call_count == 2
        mock_stop_container.assert_has_calls([call("session1"), call("session2")], any_order=True)
        assert mock_stop_container.call_count == 2
