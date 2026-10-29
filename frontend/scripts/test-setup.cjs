const { execSync } = require('child_process');
const fs = require('fs');

const pyScript = `
import zipfile
import sys
sys.stdout.reconfigure(encoding='utf-8')

zip_path = r"c:\\Users\\ThanhDz\\Downloads\\DATN_Finance\\Bachelor_Thesis_Mental_Health_Chatbot-main.zip"
with zipfile.ZipFile(zip_path, 'r') as z:
    names = z.namelist()
    front = [n for n in names if n.startswith('Bachelor_Thesis_Mental_Health_Chatbot-main/frontend/')]
    print("TOTAL FRONTEND FILES:", len(front))
    for f in front[:100]:
        print(f.replace('Bachelor_Thesis_Mental_Health_Chatbot-main/frontend/', ''))
`;

fs.writeFileSync('scripts/tmp_inspect.py', pyScript, 'utf-8');
try {
  const out = execSync('python scripts/tmp_inspect.py', { encoding: 'utf-8' });
  console.log(out);
} catch (e) {
  console.error(e.message);
} finally {
  if (fs.existsSync('scripts/tmp_inspect.py')) fs.unlinkSync('scripts/tmp_inspect.py');
}
