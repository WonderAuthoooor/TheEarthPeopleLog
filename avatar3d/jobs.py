"""SQLite任务账本；不可变请求、事务领取、崩溃恢复、重试另建任务。"""
from pathlib import Path
from contextlib import closing
from datetime import datetime
import json,sqlite3,uuid
from .contracts import RenderSpec

def now():return datetime.now().astimezone().isoformat()

class Jobs:
    def __init__(self,workspace):
        self.workspace=Path(workspace);self.workspace.mkdir(parents=True,exist_ok=True)
        self.path=self.workspace/'jobs.sqlite3'
        with closing(self.connect()) as c:
            version=c.execute('PRAGMA user_version').fetchone()[0]
            if version>2:raise ValueError('工作区数据库来自更新版本，不能用旧程序修改。')
            c.executescript('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT "", created TEXT NOT NULL, updated TEXT NOT NULL);')
            if version==0:c.execute('PRAGMA user_version=1')

    def connect(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row
        return c

    def add(self,spec):
        request=json.dumps(spec.to_dict(),ensure_ascii=False,sort_keys=True);ident=uuid.uuid4().hex
        with closing(self.connect()) as c,c:
            c.execute('INSERT INTO jobs(id,request,status,created,updated) VALUES(?,?,?,?,?)',(ident,request,'queued',now(),now()))
            if spec.schema==2:c.execute('PRAGMA user_version=2')
        return ident

    def get(self,ident):
        with closing(self.connect()) as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
        if not row:raise KeyError(ident)
        result=dict(row);result['request']=json.loads(result['request']);return result

    def list(self):
        with closing(self.connect()) as c:return [dict(r) for r in c.execute('SELECT id,status,progress,error,created FROM jobs ORDER BY created DESC LIMIT 100')]

    def next_queued(self):
        with closing(self.connect()) as c:
            row=c.execute('SELECT id FROM jobs WHERE status="queued" ORDER BY created LIMIT 1').fetchone()
            return row['id'] if row else None

    def matching(self,spec,states):
        allowed={'queued','running','complete','failed','cancelled','interrupted'}
        if not states or any(state not in allowed for state in states):raise ValueError('任务状态无效。')
        request=json.dumps(spec.to_dict(),ensure_ascii=False,sort_keys=True)
        placeholders=','.join('?' for _ in states)
        with closing(self.connect()) as c:
            row=c.execute(f'SELECT id FROM jobs WHERE request=? AND status IN ({placeholders}) ORDER BY created DESC LIMIT 1',
                          (request,*states)).fetchone()
            return row['id'] if row else None

    def claim(self,ident):
        spec=RenderSpec.from_dict(self.get(ident)['request'])
        with closing(self.connect()) as c,c:
            n=c.execute('UPDATE jobs SET status="running",updated=? WHERE id=? AND status="queued"',(now(),ident)).rowcount
            if n!=1:raise ValueError('该任务已经执行或被其他工作进程领取。')
        return spec

    def progress(self,ident,value):
        with closing(self.connect()) as c,c:
            c.execute('UPDATE jobs SET progress=?,updated=? WHERE id=? AND status="running"',(max(0,min(99,int(value))),now(),ident))

    def finish(self,ident,status,error=''):
        if status not in ('complete','failed','cancelled'):raise ValueError('非法终态。')
        with closing(self.connect()) as c,c:
            n=c.execute('UPDATE jobs SET status=?,progress=CASE WHEN ?="complete" THEN 100 ELSE progress END,error=?,updated=? WHERE id=? AND status="running"',(status,status,str(error)[:4000],now(),ident)).rowcount
            if n!=1:raise ValueError('只能结束正在运行的任务。')

    def recover(self):
        # 仅持工作区排他运行锁的应用启动时调用，不能与活跃worker并发恢复。
        with closing(self.connect()) as c,c:
            return c.execute('UPDATE jobs SET status="interrupted",error="程序退出中断；可重试生成新任务",updated=? WHERE status="running"',(now(),)).rowcount

    def retry(self,ident):
        row=self.get(ident)
        if row['status'] not in ('failed','cancelled','interrupted'):raise ValueError('只重试失败、取消或中断任务。')
        return self.add(RenderSpec.from_dict(row['request']))
