# 工作流管理系统

## 项目概述

该系统实现了一个基本的工作流运作，包括每个流中特定角色或人员的指定，不同步骤的审核方式的不同，同时支持动态化表单的生成（基于JSON）。

## 运行环境及使用方法

创建Python虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

运行应用

```bash
uvicorn doccapi.main:app --port 8000 --reload

```