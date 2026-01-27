import ast
import hashlib
import os
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

class HeuristicGuard:
    """Filters repositories/files before expensive AI calls."""

    def __init__(self, blocked_exts: List[str] = None):
        self.blocked_exts = blocked_exts or [
            ".png", ".jpg", ".jpeg", ".gif", ".exe", ".bin", ".lock",
            ".svg", ".pyc", ".zip", ".tar", ".gz", ".pdf"
        ]

    def should_analyze_file(self, file_path: str, size_bytes: int) -> bool:
        if any(file_path.endswith(ext) for ext in self.blocked_exts):
            return False
        # Limit size (e.g. 50KB) to avoid token explosion
        if size_bytes > 50 * 1024:
            return False
        return True

    def check_repo_health(self, repo_data: Dict) -> bool:
        """
        Heuristic check for repo quality based on metadata.
        Returns False if repo seems irrelevant or low quality.
        """
        # Example heuristics
        if repo_data.get("archived", False):
            return False
        # if repo_data.get("stargazers_count", 0) < 5: return False
        return True

class ASTFingerprinter(ast.NodeTransformer):
    """
    Normalizes AST to create structural fingerprint.
    Replaces variable names with generics.
    """

    def visit_Name(self, node):
        # Replace all variable names with 'VAR'
        return ast.copy_location(ast.Name(id='VAR', ctx=node.ctx), node)

    def visit_arg(self, node):
        # Replace argument names
        return ast.copy_location(ast.arg(arg='ARG', annotation=None), node)

    def visit_FunctionDef(self, node):
        # Anonymize function name but keep structure
        self.generic_visit(node)
        # We might want to keep function names for some semantic context,
        # but for pure structural clone detection, we anonymize.
        node.name = 'FUNC'
        # Clean defaults to avoid diffs on values
        node.args.defaults = []
        return node

    # Remove Docstrings and Constants?
    # Keeping logic structure is key.
    def visit_Constant(self, node):
        # Replace all constants (strings, numbers) with a placeholder
        # This makes it ignore "magic numbers" or string variations
        return ast.copy_location(ast.Constant(value='CONST'), node)

    def get_fingerprint(self, source_code: str) -> str:
        try:
            tree = ast.parse(source_code)
            normalized = self.visit(tree)
            dump = ast.dump(normalized)
            return hashlib.md5(dump.encode()).hexdigest()
        except SyntaxError:
            return "SYNTAX_ERROR"
        except Exception:
            return "ERROR"

class CodeAnalyzer:
    def __init__(self):
        self.fingerprinter = ASTFingerprinter()
        self.baseline_fingerprints: Set[str] = set()

    def index_project(self, root_path: str):
        """Index local project to establish baseline for clone detection."""
        count = 0
        for root, _, files in os.walk(root_path):
            if "venv" in root or ".git" in root or "__pycache__" in root or "node_modules" in root:
                continue
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8") as file:
                            content = file.read()
                            fp = self.fingerprinter.get_fingerprint(content)
                            if fp not in ["SYNTAX_ERROR", "ERROR"]:
                                self.baseline_fingerprints.add(fp)
                                count += 1
                    except Exception:
                        pass
        logger.info(f"Indexed {count} local files for baseline.")

    def analyze_file(self, content: str) -> Dict[str, Any]:
        """Deep analysis of a single file content."""
        fp = self.fingerprinter.get_fingerprint(content)

        is_clone = fp in self.baseline_fingerprints

        # Calculate complexity (simplified Cyclomatic approximation)
        # Count branching nodes
        complexity = (
            content.count("if ") +
            content.count("for ") +
            content.count("while ") +
            content.count("except ") +
            content.count("with ")
        )

        return {
            "fingerprint": fp,
            "is_known_clone": is_clone,
            "complexity_score": complexity,
            "loc": len(content.splitlines())
        }
