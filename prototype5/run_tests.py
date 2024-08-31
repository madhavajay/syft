import os
import time

def run_pytest():
    """Run pytest and return the result."""
    return os.system('pytest > /dev/null 2>&1') == 0

def run_coverage():
    """Run pytest with coverage and return the coverage percentage."""
    # Run pytest with coverage
    stream = os.popen('pytest --cov=. --cov-report=term-missing:skip-covered')
    output = stream.read()
    print("Coverage output:")
    print(output)
    # Parse the output to find the total coverage
    for line in output.split('\n'):
        if line.startswith('TOTAL'):
            return line.split()[-1].rstrip('%')
    return "N/A"

def update_display(iteration, status, coverage):
    """Update the display with the current status."""
    status_text = "All tests passed" if status else "Some tests failed"
    status_color = "\033[92m" if status else "\033[91m"  # Green if passed, Red if failed
    return f"\rIteration: {iteration} | Last run: {time.strftime('%H:%M:%S')} | Status: {status_color}{status_text}\033[0m | Coverage: \033[94m{coverage}%\033[0m    "

def main():
    print("Continuous pytest runner with coverage started. Press Ctrl+C to stop.")
    print("==================================================================")
    
    iteration = 0
    try:
        while True:
            iteration += 1
            
            status = run_pytest()
            coverage = run_coverage()
            
            print(update_display(iteration, status, coverage), end='', flush=True)
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nContinuous pytest runner stopped.")

if __name__ == "__main__":
    main()