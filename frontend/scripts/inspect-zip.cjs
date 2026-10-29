const { execSync } = require('child_process');
const fs = require('fs');

const pyScript = `
import zipfile

zip_path = r"c:\\Users\\ThanhDz\\Downloads\\DATN_Finance\\Bachelor_Thesis_Mental_Health_Chatbot-main.zip"
with zipfile.ZipFile(zip_path, 'r') as z:
    names = z.namelist()
    print("TOTAL:", len(names))
    front = [n for n in names if any(k in n.lower() for k in ['frontend', 'web', 'ui', 'client', 'app', 'static', 'templates'])]
    print("FRONTEND/WEB COUNT:", len(front))
    for f in front[:100]:
        print(f)
`;

fs.writeFileSync('scripts/tmp_inspect.py', pyScript);
try {
  const out = execSync('python scripts/tmp_inspect.py', { encoding: 'utf-8' });
  console.log(out);
} catch (e) {
  console.error(e.message);
} finally {
  if (fs.existsSync('scripts/tmp_inspect.py')) fs.unlinkSync('scripts/tmp_inspect.py');
}
