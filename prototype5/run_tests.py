import os
import time
import subprocess
import sys

def run_pytest():
    """Run pytest and return the result."""
    return subprocess.call(['pytest'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def run_coverage():
    """Run pytest with coverage and return the coverage percentage."""
    result = subprocess.run(['pytest', '--cov=.', '--cov-report=term-missing:skip-covered'], 
                            capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if line.startswith('TOTAL'):
            return line.split()[-1].rstrip('%')
    return "N/A"

def get_git_status():
    """Get the status of the git repository."""
    try:
        output = subprocess.check_output(['git', 'status', '--porcelain'], stderr=subprocess.DEVNULL).decode('utf-8').strip()
        lines = output.split('\n')
        staged = sum(1 for line in lines if line.startswith('M '))
        unstaged = sum(1 for line in lines if line.startswith(' M'))
        untracked = sum(1 for line in lines if line.startswith('??'))
        return staged, unstaged, untracked
    except subprocess.CalledProcessError:
        return 0, 0, 0

def git_status_symbol(staged, unstaged, untracked):
    """Return a symbol representing the git status."""
    total = staged + unstaged + untracked
    if total == 0:
        return "\033[92m●\033[0m"  # Green dot for clean repo
    elif total < 5:
        return "\033[93m▲\033[0m"  # Yellow triangle for few changes
    elif total < 10:
        return "\033[91m■\033[0m"  # Red square for several changes
    else:
        return "\033[91m★\033[0m"  # Red star for many changes

def update_display(iteration, status, coverage, staged, unstaged, untracked):
    """Update the display with the current status."""
    status_color = "\033[92m" if status else "\033[91m"  # Green if passed, Red if failed
    status_symbol = "✓" if status else "✗"
    time_str = time.strftime('%H:%M:%S')
    git_symbol = git_status_symbol(staged, unstaged, untracked)
    
    output = f"\033[2J\033[H"  # Clear screen and move cursor to top-left
    output += "Continuous pytest runner\n"
    output += "Press Ctrl+C to stop.\n"
    output += "-" * 10 + "\n"
    output += f"I:{iteration}\n"
    output += f"T:{time_str}\n"
    output += f"S:{status_color}{status_symbol}\033[0m\n"
    output += f"C:\033[94m{coverage}%\033[0m\n"
    output += f"G:{git_symbol}\n"
    if staged + unstaged + untracked > 0:
        output += f"+{staged}~{unstaged}?{untracked}\n"
    output += "-" * 10 + "\n"
    
    sys.stdout.write(output)
    sys.stdout.flush()

def main():
    iteration = 0
    try:
        while True:
            iteration += 1
            
            status = run_pytest()
            coverage = run_coverage()
            staged, unstaged, untracked = get_git_status()
            
            update_display(iteration, status, coverage, staged, unstaged, untracked)
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()