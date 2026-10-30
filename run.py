"""Windows/macOS/Linux local runner. Visit /setup on first launch."""
import os
import uvicorn
if __name__=='__main__':
 uvicorn.run('app.main:app',host=os.environ.get('CYPLUS_HOST','127.0.0.1'),port=int(os.environ.get('CYPLUS_PORT','8787')),reload=False,proxy_headers=False)
