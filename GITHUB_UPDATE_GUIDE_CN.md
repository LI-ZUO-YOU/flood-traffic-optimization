# GitHub增量更新使用说明

把本地github_update文件夹**里面的内容**合并到原仓库根目录，保留内部路径。不要把整个github_update再嵌套成仓库下的同名目录。

1. 保留原仓库，不清空、不删除旧tag/release。
2. README.md是更新后的首页，替换原README.md。
3. MANIFEST.sha256是旧文件加新增文件的完整校验清单，替换原同名清单。
4. revision_R1、revision_R2、tools内的新文件及根目录REVISION_*说明/索引、config/revision_archive_locations.json，按路径新增。原code、data、results、surrogate及冻结config文件不替换。
5. 只上传本github_update目录的内容。旁边github_update_audit是本地审核与校验记录，不上传；之前的private_review、audit及三份marked Word也不加进代码仓库。
6. 本目录仅为GitHub源码与主要统计结果增量，完整原始材料仍属于Zenodo版本包。S14的Bootstrap CSV已直接放入对应位置。
7. 新版Zenodo具体DOI取得并核实后，更新config/revision_archive_locations.json、README和论文中的对应引用。旧DOI不能代称新数据已公开。

检查命令：python tools/verify_github_update.py --mode overlay；合并后再用--mode merged。不要为了更新仓库重新运行UE、训练或正式优化。

本次仅在本地准备，没有提交、推送、发布GitHub Release或上传Zenodo。新Release若会自动触发Zenodo，发布前应与完整数据归档安排一致。
