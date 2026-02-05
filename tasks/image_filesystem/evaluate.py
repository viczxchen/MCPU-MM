"""
Evaluation function for image_filesystem task.

This evaluator checks if the agent has correctly classified images into three folders:
- comic_meme
- animal_meme  
- human_meme

The evaluation compares the actual file structure in the container with the ground truth.
"""
import os
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Set


# Ground truth: expected files in each category
GROUND_TRUTH: Dict[str, Set[str]] = {
    "comic_meme": {
        # "15120.jpg",
        # "15155.jpg",
        "15157.jpg",
        # "15160.jpg",
    },
    "animal_meme": {
        # "15130.jpg",
        "15146.jpg",
    },
    "human_meme": {
        "15097.jpg",
        # "15098.jpg",
        # "15100.jpg",
        # "15103.jpg",
        # "15105.jpg",
        # "15109.jpg",
        # "15111.jpg",
        # "15113.jpg",
        # "15121.jpg",
        # "15143.jpg",
        # "15147.jpg",
        # "15158.jpg",
    },
}


def get_container_name(task_name: str) -> str:
    """
    Get the Docker container name for a task.
    
    Note: This is a fallback function. The actual container name should
    be passed from runner.py which extracts it from docker-compose.yaml.
    """
    # Fallback format (should match docker-compose.yaml pattern)
    return f"mcpu-mm-image-filesystem-{task_name}"


def check_container_filesystem(container_name: str, workspace_path: str = "/workspace/meme_data") -> Tuple[bool, str]:
    """
    Check the file system structure inside the Docker container.
    
    Args:
        container_name: Name of the Docker container
        workspace_path: Path to workspace inside container (default: /workspace)
        
    Returns:
        Tuple of (passed: bool, error_message: str)
    """
    # Check if container is running
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if container_name not in result.stdout:
            return False, f"Container {container_name} is not running"
    except Exception as e:
        return False, f"Failed to check container status: {e}"
    
    errors = []
    
    # Check each expected folder
    for folder_name, expected_files in GROUND_TRUTH.items():
        folder_path = f"{workspace_path}/{folder_name}"
        
        # Check if folder exists
        try:
            result = subprocess.run(
                ["docker", "exec", container_name, "test", "-d", folder_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                errors.append(f"Folder '{folder_name}' does not exist")
                continue
        except Exception as e:
            errors.append(f"Failed to check folder '{folder_name}': {e}")
            continue
        
        # List files in the folder
        try:
            result = subprocess.run(
                ["docker", "exec", container_name, "find", folder_path, "-type", "f", "-name", "*.jpg"],
                capture_output=True,
                text=True,
                check=True,
            )
            actual_files = set()
            for line in result.stdout.strip().split("\n"):
                if line:
                    # Extract just the filename from the full path
                    filename = Path(line).name
                    actual_files.add(filename)
            
            # Check if all expected files are present
            missing_files = expected_files - actual_files
            if missing_files:
                errors.append(
                    f"Folder '{folder_name}' is missing files: {', '.join(sorted(missing_files))}"
                )
            
            # Check for unexpected files (optional - you might want to allow extra files)
            extra_files = actual_files - expected_files
            if extra_files:
                errors.append(
                    f"Folder '{folder_name}' has unexpected files: {', '.join(sorted(extra_files))}"
                )
                
        except subprocess.CalledProcessError as e:
            errors.append(f"Failed to list files in '{folder_name}': {e}")
        except Exception as e:
            errors.append(f"Error checking folder '{folder_name}': {e}")
    
    if errors:
        return False, "; ".join(errors)
    
    return True, "All images correctly classified into the three folders"


def verify(test_dir: Path, container_name: str = None) -> Tuple[bool, str]:
    """
    Main verification function.
    
    Args:
        test_dir: Path to the task directory (on host)
        container_name: Optional container name. If not provided, will be inferred from task name.
        
    Returns:
        Tuple of (passed: bool, error_message: str)
    """
    if container_name is None:
        # Infer container name from task directory or environment
        task_name = test_dir.name
        container_name = get_container_name(task_name)
    
    return check_container_filesystem(container_name)


if __name__ == "__main__":
    # For testing
    import sys
    if len(sys.argv) > 1:
        test_dir = Path(sys.argv[1])
    else:
        test_dir = Path(__file__).parent
    
    container_name = os.environ.get("DOCKER_CONTAINER_NAME")
    passed, msg = verify(test_dir, container_name)
    if passed:
        print("✅ Verification passed!")
        sys.exit(0)
    else:
        print(f"❌ Verification failed: {msg}")
        sys.exit(1)

