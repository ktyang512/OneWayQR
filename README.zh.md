# 使用 QR 码单向传输（Python）

用于通过 QR 码序列进行单向数据传输的 MVP，支持多 QR 网格、基础 XOR 冗余和完整性校验。

## 快速开始
- 安装依赖：`pip install -e .`（若后续需要更强 FEC，可额外安装 `pip install reedsolo`）。
- 发送（窗口显示）：`qrc send /path/to/file --grid-rows 2 --grid-cols 2 --fps 10`
- 发送到 MP4（无窗口）：`qrc send /path/to/dir --compress --no-display --video-output out.mp4`
- 摄像头接收：`qrc receive --extract --output out_dir`
- 从视频接收：`qrc receive --input out.mp4 --extract --output out_dir`

## 说明
- 负载：文件原样发送；目录会打包为 tar（可选 gzip 压缩）。`--compress` 对整体负载做 gzip（QR 内已含 ECC，仍建议按场景决定）。
- 帧与校验：自定义帧头 + CRC32，session header 重复插入；数据块分组为超级块，使用 XOR 冗余（每个超级块可恢复 1 个缺失块）。
- 吞吐调优：默认分片大小较保守（512 字节，base64 后体积更大）。可调 `--chunk-size`、`--grid-rows/cols`、`--fps`；较小分片通常更稳。
- QR 生成：使用 `segno`（ECC 级别 H），按固定网格组合；OpenCV 窗口渲染帧并可写入 MP4。
- 解码：OpenCV `detectAndDecodeMulti` 在摄像头/视频上识别；base64 -> 帧解析 -> 重组；提取前验证整体 SHA256。

## 法律与合规声明
- 预期用途：合法、合规的研究、教育及允许单向/离线传输的场景，需遵守当地法规。
- 禁止用途：任何违法、恶意、侵犯隐私或权益的使用；在法规或政策不允许的场景下部署。
- 无担保与免责：本项目按“原样”提供，维护者不对任何损失或第三方滥用承担责任。
- 合规责任：使用者需自行确保安全、隐私、出口管制及行业合规。

## 限制与后续
- 目前 FEC 仅为基础 XOR，可引入 Reed-Solomon 以提升多块丢失恢复能力。
- 暂无自适应曝光/布局检测，依赖稳定光照与对焦。
- 尚未支持可恢复/断点续播；一次播发需完整录制。
- base64 增加约 33% 体积；需根据显示/摄像头条件调节分片大小。

## 同步维护
本中文版内容与英文版 `README.md` 需保持同步更新。*** End Patch ***!
