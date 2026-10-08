import unittest
from unittest.mock import patch
import verify_release

class VersionGateTests(unittest.TestCase):
    def test_python_313_refused_before_file_reads_or_tests(self):
        with patch.object(verify_release.sys,'version_info',(3,13,0)),patch.object(verify_release.pathlib.Path,'read_text') as read,patch.object(verify_release.subprocess,'run') as run:
            with self.assertRaisesRegex(SystemExit,'supported interpreter is Python 3.12; Python 3.13 is unsupported'):
                verify_release.main()
            read.assert_not_called();run.assert_not_called()
    def test_other_unsupported_interpreter_refused(self):
        with patch.object(verify_release.sys,'version_info',(3,14,0)):
            with self.assertRaisesRegex(SystemExit,'Python 3.14 is unsupported'):verify_release.main()

if __name__=='__main__':unittest.main()
