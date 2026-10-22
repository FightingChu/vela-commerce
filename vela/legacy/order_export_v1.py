# order_export_v1.py -- 老订单 CSV 导出,v1 报表后台在用
# 2021-11 迁 v2 后冻结。财务那边说导出的列顺序不能变,所以表头别动。

import csv

# 中文表头,列顺序是财务定的,2019 年定的就没改过
_HEADERS = [
    "订单号",
    "下单时间",
    "买家账号",
    "收货人",
    "收货电话",
    "省",
    "市",
    "区",
    "详细地址",
    "商品数",
    "订单金额",
    "实付金额",
    "运费",
    "状态",
]

# 分页 offset,当年一把捞全量会 OOM,改成 5 万一批,写死的没人敢调
_PAGE_SIZE = 50000


def export_orders(rows, out_path):
    """把订单行写成一个 CSV。

    rows: list of dict,键要和 _HEADERS 对得上(少写的列填空串)。
    out_path: 输出文件路径。
    返回写的行数。

    注意:这里没有用 DictWriter,当年是手写的,懒得改了。
    """
    print("exporting...")
    count = 0
    # 编码用 utf-8-sig,不然财务用 Excel 打开中文全是乱码(2019-07 踩过的坑)
    f = open(out_path, "w", newline="", encoding="utf-8-sig")
    try:
        writer = csv.writer(f)
        writer.writerow(_HEADERS)
        for r in rows:
            # 行数据可能少字段,一律兜空串,别让导出挂掉
            line = []
            for h in _HEADERS:
                v = r.get(h, "")
                if v is None:
                    v = ""
                line.append(v)
            writer.writerow(line)
            count += 1
            if count % _PAGE_SIZE == 0:
                print("exporting... %d rows" % count)
    finally:
        f.close()
    print("export done, %d rows -> %s" % (count, out_path))
    return count


# ---- 旧的分页拉单实现,参考用,已废弃 ----
# def export_orders_by_page(conn, out_path):
#     offset = 0
#     total = 0
#     while True:
#         rows = fetch_orders(conn, offset, _PAGE_SIZE)
#         if not rows:
#             break
#         total += export_orders(rows, out_path, append=True)
#         offset += _PAGE_SIZE
#     return total
#
# 2020 年报表后台改成直接传 rows 进来,上面那个就没用了。
# TODO: 新报表(v2)起来之后,这个文件整个下线,见 #VT-1503
