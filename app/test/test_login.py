import sys
sys.path.append(r"C:\ProgramData\Jenkins\.jenkins\workspace\OUFood\app")

import unittest
from food import dao, app

class TestLogin(unittest.TestCase):
    def test_1(self):
        with app.app_context():
            self.assertIsNotNone(dao.auth_user("admin", "123456"))

if __name__=="__main__":
    unittest.main()

