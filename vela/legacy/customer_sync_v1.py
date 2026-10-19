# -*- coding: utf-8 -*-
# customer_sync_v1.py -- 客户同步老脚本入口
# 2021-11 迁 v2 后冻结。原先是 crontab 半夜 2 点跑,写死读 /data/export/customer.csv,
# 现在机器上那个文件早没了,脚本留在仓库里纯粹是当"行为参考"用的——
# v2 的同步任务有时要对 2019-2021 的同步结果做回溯,得知道当时字段怎么处理的。

import csv


# 写死的路径,2019 年的 /data 挂载,现在肯定不存在了
_INPUT_PATH = "/data/export/customer.csv"

# 同步批次大小,当年 MySQL 从库的读取窗口就这么大
_BATCH_SIZE = 200


def _norm_phone(raw):
    """手机号清洗:去空格、去 +86 前缀。

    坑:老 CSV 里有人把座机也填进来了(带区号的),v1 没校验,原样入库。
    """
    if raw is None:
        return ""
    s = str(raw).strip().replace(" ", "").replace("-", "")
    if s.startswith("+86"):
        s = s[3:]
    return s


def sync_batch(batch):
    """同步一批客户记录。

    FIXME: 只处理了一半字段——phone/email/nickname 先接进来,
    地址相关的(receiver_*)当时说要等地址库重构,一直没接,就直接丢掉了。
    2019-12 挂在这里,后来赶双十一上线,地址同步走的是另一个临时脚本(已失传)。

    返回成功条数。
    """
    ok = 0
    for rec in batch:
        # 只同步这些字段,其他全丢(见 FIXME)
        item = {
            "customer_id": rec.get("id"),
            "phone": _norm_phone(rec.get("mobile")),
            "email": (rec.get("email") or "").strip().lower(),
            "nickname": (rec.get("nick_name") or "").strip(),
        }
        # TODO: 这里当年是写老库,现在是冻结节选,只打日志
        print("[sync_v1] would sync: %s" % item["customer_id"])
        ok += 1
    return ok


def main():
    """老入口。crontab: 30 2 * * * python -m scripts.customer_sync"""
    print("[sync_v1] start, input=%s" % _INPUT_PATH)
    try:
        f = open(_INPUT_PATH, "r", encoding="utf-8-sig")
    except IOError as e:
        print("[sync_v1] input not found, exit: %s" % e)
        return 1
    try:
        reader = csv.DictReader(f)
        batch = []
        total = 0
        for row in reader:
            batch.append(row)
            if len(batch) >= _BATCH_SIZE:
                total += sync_batch(batch)
                print("[sync_v1] progress: %d rows" % total)
                batch = []
        if batch:
            total += sync_batch(batch)
        print("[sync_v1] done, total=%d" % total)
    except Exception as e:
        # 老行为:任何异常都不让 crontab 报警,当年怕半夜被 call
        print("[sync_v1] failed, swallowed: %s" % e)
        return 1
    finally:
        f.close()
    return 0


if __name__ == "__main__":
    main()

# 历史:2019-10 建,作者是当时的数据组实习生(已离职),注释比代码多。
# 2021-11 迁 v2 后冻结,见 #VT-1503。
