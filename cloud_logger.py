import logging
from google.cloud import storage

class CloudLogger(logging.Handler):
    def __init__(self, bucket_name, log_file_name):
        super().__init__()
        self.client = storage.Client()
        self.bucket = self.client.get_bucket(bucket_name)
        self.blob = self.bucket.blob(log_file_name)

    def emit(self, record):
        log_entry = self.format(record) + '\n'
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
