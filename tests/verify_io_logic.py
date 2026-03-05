import asyncio
import os
import sys
from unittest.mock import MagicMock

# Mock dependencies that might be missing
sys.modules['tuner.hunter'] = MagicMock()
sys.modules['tuner.agent.perception'] = MagicMock()

from tuner.agent.tools import AgentTools

async def test_read_write_functionality():
    tools = AgentTools()
    test_path = "test_io.txt"
    test_content = "Hello, World!"

    # Clean up
    if os.path.exists(test_path): os.remove(test_path)
    if os.path.exists(test_path + ".bak"): os.remove(test_path + ".bak")

    print("Testing write_file...")
    res = await tools.write_file(test_path, test_content)
    print(res)
    assert "Success" in res
    assert os.path.exists(test_path)
    with open(test_path, "r") as f:
        assert f.read() == test_content

    print("Testing read_file...")
    content = await tools.read_file(test_path)
    assert content == test_content
    print("Read content successfully.")

    print("Testing backup creation...")
    new_content = "New Content"
    res = await tools.write_file(test_path, new_content)
    print(res)
    assert os.path.exists(test_path + ".bak")
    with open(test_path + ".bak", "r") as f:
        assert f.read() == test_content
    with open(test_path, "r") as f:
        assert f.read() == new_content
    print("Backup verified.")

    print("Testing nested directory creation...")
    nested_path = "subdir/test_nested.txt"
    res = await tools.write_file(nested_path, "Nested")
    print(res)
    assert os.path.exists(nested_path)
    print("Nested directory creation verified.")

    print("Testing error handling (absolute path)...")
    res = await tools.read_file("/etc/passwd")
    assert "Error" in res
    print("Absolute path check verified.")

    # Cleanup
    if os.path.exists(test_path): os.remove(test_path)
    if os.path.exists(test_path + ".bak"): os.remove(test_path + ".bak")
    if os.path.exists(nested_path): os.remove(nested_path)
    if os.path.exists("subdir"): os.rmdir("subdir")

    print("\nAll functionality tests passed!")

if __name__ == "__main__":
    asyncio.run(test_read_write_functionality())
