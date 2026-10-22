# dockbuddy-models

DockBuddy 打分模型资源管理「壳子」 —— 把「模型注册表 + 资产下载 + 缓存 + 路径配置」从 DockBuddy 项目里**解耦**成独立可复用的 Python 库。

**本库不含任何具体模型数据** —— 模型注册表是外部 JSON 配置文件，使用时单独传入，库只保留逻辑壳子。

- **纯壳子**：模型数据(权重清单/源码单元/依赖)由调用方提供，库不绑定任何模型。
- **多类型资产下载**：权重/源码/工具，手动/自动，幂等，校验，解压，锁定。
- **来源抽象**：COS(内网/公网) / URL / HF / git。
- **路径配置**：资源总根、权重根、源码根、工具根、缓存全部可配。
- **解耦**：只依赖 `cos-python-sdk-v5` + 标准库，不 import 任何 DockBuddy 代码。

## 安装

```bash
pip install dockbuddy-models \
  --index-url https://pypi.cnb.cool/vcinex/bioinfo/-/packages/simple
```

## 快速开始

```python
from dockbuddy_models import ModelHub

hub = ModelHub(models="/path/to/models.json",   # 模型数据配置文件(外部传入)
               root="/data/dockbuddy")          # 资源总根
hub.list_models()           # 全部 23 个
hub.available()             # 15 个可运行模型
hub.download("saprot")      # 下载某模型全部资产(权重+源码)
hub.download("esm2", kinds=["weights"])   # 只下权重
hub.download_all()          # 自动下载全部 available
```

## CLI

```bash
dockbuddy-models --models /path/to/models.json list --available
dockbuddy-models --models /path/to/models.json download esm2
dockbuddy-models --models /path/to/models.json download --all
dockbuddy-models --models /path/to/models.json info saprot
dockbuddy-models --models /path/to/models.json path esm2
dockbuddy-models --models /path/to/models.json lock
```

## 配置

所有路径可配置，优先级：显式参数 > 环境变量 > 默认值。

| 项 | 构造参数 | 环境变量 | 默认 |
|---|---|---|---|
| 资源总根 | `root` | `DOCKBUDDY_MODELS_ROOT` | `~/.cache/dockbuddy_models` |
| 权重下载根 | `models_root` | `DOCKBUDDY_MODELS_MODELS_ROOT` | `root/models` |
| 源码根 | `repos_root` | `DOCKBUDDY_MODELS_REPOS_ROOT` | `root/repos` |
| 本地工具根 | `tools_root` | `DOCKBUDDY_MODELS_TOOLS_ROOT` | `root/tools` |
| 缓存目录 | `cache_dir` | `DOCKBUDDY_MODELS_CACHE_DIR` | `root/cache` |
| COS 凭证 | `cos` | `DOCKBUDDY_MODELS_SECRET_ID/KEY` | 环境变量 / `~/.tccli/default.credential` |

### COS 内网（云实例，流量 0 元）

```python
from dockbuddy_models import ModelHub, CosConfig

hub = ModelHub(
    models_root="/home/ubuntu/dockbuddy/models",
    cos=CosConfig(endpoint="cos.ap-shanghai.tencentcos.cn", scheme="http"),
)
```

凭证缺省时自动从 `~/.tccli/default.credential` 或 `TENCENT_SECRET_ID/KEY` 兜底。

## 缓存

```python
hub.cached_models()     # 已缓存的模型
hub.total_size()        # 总占用字节
hub.clear_cache("esm2") # 清某模型下载记录
hub.ensure("foldx")     # 幂等确保权重就位（缺则补下）
```

## 本地工具路径

```python
hub.tool_path("foldx/foldx_20261231")     # 拼 <tools_root>/foldx/foldx_20261231
hub.resolve_tool("foldx/foldx_20261231")  # 校验存在，不存在返回 None
```

## 扩充模型（三种方式）

```python
# 1) 运行时注册
hub.register({
    "name": "mymodel",
    "assets": {
        "weights": [{"cos": "hot/mymodel/model.pt", "dest": "mymodel/model.pt"}],
        "source": [{"cos": "units/src-mymodel.tar.gz", "dest": "Mymodel", "extract": {"strip": 4, "to": "repos"}}],
    },
    "device_req": "gpu",
})

# 2) 外部 JSON 合并
hub.load_registry("/path/to/my/models.json")

# 3) 构造时指定
from dockbuddy_models import Registry
hub = ModelHub(registry=Registry.load("/path/to/my/models.json"))
```

注册表条目 schema（缺省字段自动补齐）：

```json
{
  "name": "esm2",
  "kind": "score",
  "env": "dockbuddy",
  "status": "available",
  "device_req": "any",
  "requires": {},
  "assets": {
    "weights": [{"cos": "hot/esm2/esm2_t33_650M_UR50D.pt", "dest": "esm2/esm2_t33_650M_UR50D.pt"}],
    "source": [],
    "tool": []
  },
  "params": [{"name": "model_name", "label": "模型规模", "type": "dropdown", "default": "esm2_t33_650M_UR50D"}]
}
```

三类资产 `dest` 各相对对应根：`weights`→`models_root`、`source`→`repos_root`、`tool`→`tools_root`（支持共享权重如 `esm2_hf`）。
资产条目来源四选一：`cos` / `url` / `hf` / `git`；`extract` 支持 tar.gz 解压(`strip`/`glob`/`to`)；`sha256` 声明后下载校验。

## 与 DockBuddy 的解耦关系

模型数据文件由一次性脚本 `scripts/export_registry.py` 从 DockBuddy 的 `models_registry.py` +
`deploy/models/*/model.json` 融合生成。生成的是**库外**的 `models.json`（本仓库根，**不进 wheel**），
使用时显式传入，库本身不含任何模型数据。

重新同步（DockBuddy 新增模型后）：

```bash
python scripts/export_registry.py \
  --dockbuddy /path/to/dockBuddy \
  --out models.json
```

也可用环境变量 `DOCKBUDDY_MODELS_CONFIG` 指定默认数据文件，或运行时 `hub.load_registry(...)` 合并。
