import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rag_answer import FALLBACK, RetrievedChunk, build_prompt, context_is_weak, valid_citations

def chunk(score=0.8): return RetrievedChunk("pages:test:one", "Supported fact.", "data/test.md", 0.03, score)

class GroundingTests(unittest.TestCase):
    def test_prompt(self):
        prompt = build_prompt("Question?", [chunk()])
        self.assertIn("pages:test:one", prompt); self.assertIn("Question?", prompt)
    def test_weak_context(self):
        self.assertTrue(context_is_weak([], .3)); self.assertTrue(context_is_weak([chunk(.2)], .3)); self.assertFalse(context_is_weak([chunk()], .3))
    def test_citations(self):
        self.assertTrue(valid_citations("Fact [pages:test:one]", [chunk()]))
        self.assertFalse(valid_citations("Fact", [chunk()])); self.assertFalse(valid_citations("Fact [fake:id]", [chunk()])); self.assertTrue(valid_citations(FALLBACK, []))

if __name__ == "__main__": unittest.main()
