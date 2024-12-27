import logging
from google.cloud import storage
from datetime import datetime, timedelta

class CloudLogger(logging.Handler):
    def __init__(self, bucket_name, log_file_name):
        super().__init__()
        self.client = storage.Client()
        self.bucket = self.client.get_bucket(bucket_name)
        self.blob = self.bucket.blob(log_file_name)

    def emit(self, record):
        # Get the UTC time, and then adjust it to IST (UTC + 5:30)
        utc_time = datetime.utcnow()
        ist_time = utc_time + timedelta(hours=5, minutes=30)

        # Format the time in the desired format
        log_time = ist_time.strftime('%Y-%m-%d %H:%M:%S')

        # Create the log message with the IST timestamp
        log_entry = f'{log_time} - {self.format(record)}\n'

        # Read current logs from the storage, append new log, and write back
        current_logs = self._read_logs()
        current_logs += log_entry
        self._write_logs(current_logs)

    def _read_logs(self):
        try:
            # Download the current log file (if it exists)
            return self.blob.download_as_text()
        except Exception:
            return ""  # If no logs exist, return an empty string

    def _write_logs(self, logs):
        # Upload the updated logs to Google Cloud Storage
        self.blob.upload_from_string(logs)