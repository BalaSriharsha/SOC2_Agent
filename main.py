import sys
from agent import SOC2Agent

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py '<your SOC2 prompt>'")
        sys.exit(1)
    
    prompt = sys.argv[1]
    agent = SOC2Agent()
    agent.process_prompt(prompt)

if __name__ == "__main__":
    main()
