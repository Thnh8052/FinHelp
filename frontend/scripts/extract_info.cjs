const { execSync } = require('child_process');
const fs = require('fs');

const pyScript = `
import zipfile

zip_path = r"c:\\Users\\ThanhDz\\Downloads\\DATN_Finance\\Bachelor_Thesis_Mental_Health_Chatbot-main.zip"
with zipfile.ZipFile(zip_path, 'r') as z:
    # Read README.md
    try:
        readme = z.read('Bachelor_Thesis_Mental_Health_Chatbot-main/README.md').decode('utf-8', errors='ignore')
        with open('scripts/THESIS_README.md', 'w', encoding='utf-8') as f:
            f.write(readme)
        print("Wrote THESIS_README.md")
    except Exception as e:
        print("Err readme:", e)

    # Read frontend file list
    front_files = [n for n in z.namelist() if 'frontend' in n]
    with open('scripts/FRONTEND_FILES.txt', 'w', encoding='utf-8') as f:
        f.write('\\n'.join(front_files))
    print("Wrote FRONTEND_FILES.txt, total:", len(front_files))
`;

fs.writeFileSync('scripts/tmp_py.py', pyScript, 'utf-8');
try {
  execSync('python scripts/tmp_py.py', { stdio: 'inherit' });
} catch (e) {
  console.error('Python error:', e.message);
} finally {
  if (fs.existsSync('scripts/tmp_py.py')) fs.unlinkSync('scripts/tmp_py.py');
}
