import os

def validate_files():
    files = [
        '/home/alucard/Downloads/AI Bot/Antigravity_Project_Handoff.docx',
        '/home/alucard/Downloads/AI Bot/Abdul_Project_Explainer.docx'
    ]
    
    for f in files:
        if not os.path.exists(f):
            print(f"FAILED: File not found: {f}")
            return False
        
        # Check size to ensure it's not empty
        size = os.path.getsize(f)
        if size < 1000:
            print(f"FAILED: File {f} exists but seems suspiciously small ({size} bytes).")
            return False
            
        print(f"SUCCESS: {f} validated successfully. Size: {size} bytes.")
        
    return True

if __name__ == '__main__':
    print("Validating generated Word documents...")
    validate_files()
