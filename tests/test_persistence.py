
import sys
import unittest
from pathlib import Path
from src.mcp_server.tools import add_pending_prompt, get_pending_prompts_list, clear_pending_prompts, PROMPTS_FILE

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Clear any existing prompts
        if PROMPTS_FILE.exists():
            PROMPTS_FILE.unlink()

    def tearDown(self):
        # Clean up
        if PROMPTS_FILE.exists():
            PROMPTS_FILE.unlink()

    def test_add_and_retrieve_prompt(self):
        prompt_text = "Test prompt"
        add_pending_prompt(prompt_text)
        
        prompts = get_pending_prompts_list()
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]['prompt'], prompt_text)

    def test_clear_prompts(self):
        add_pending_prompt("Test prompt")
        clear_pending_prompts()
        
        prompts = get_pending_prompts_list()
        self.assertEqual(len(prompts), 0)

if __name__ == '__main__':
    unittest.main()
