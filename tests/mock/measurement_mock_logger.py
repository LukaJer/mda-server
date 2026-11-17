import sys
import logging

MeasurementMockLogger = logging.getLogger()
MeasurementMockLogger.setLevel(logging.DEBUG)

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.INFO)
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_stdout_handler.setFormatter(_formatter)
MeasurementMockLogger.addHandler(_stdout_handler)
