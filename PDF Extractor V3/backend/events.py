"""
events.py — SocketIO event name constants shared by backend and referenced in frontend.
"""

# Sync events
SYNC_LOG  = "sync:log"
SYNC_DONE = "sync:done"

# Scan events
SCAN_PROGRESS = "scan:progress"
SCAN_DONE     = "scan:done"

# Extract events
EXTRACT_PROGRESS = "extract:progress"
EXTRACT_RESULT   = "extract:result"
EXTRACT_DONE     = "extract:done"
