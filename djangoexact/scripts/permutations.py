from itertools import product

SUFFIX_START = "_start"
SUFFIX_W = "_w"


def _by_key(items, key_fn):
    items = list(items)
    ids = []
    by_id = {}
    for o in items:
        k = key_fn(o) if callable(key_fn) else getattr(o, key_fn, o)
        ids.append(k)
        by_id[k] = o
    return ids, by_id


def one_change_combinations(fields_dict, key_fn=lambda o: getattr(o, "pk", o)):
    """
    Returns a single dict per combination, keeping original keys (e.g. _start/_w/static).
    For each combination, exactly one pair differs between _start and _w.
    """
    bases, statics = {}, {}
    for k, v in fields_dict.items():
        if k.endswith(SUFFIX_START):
            base = k[: -len(SUFFIX_START)]
            bases.setdefault(base, {})["start"] = list(v)
        elif k.endswith(SUFFIX_W):
            base = k[: -len(SUFFIX_W)]
            bases.setdefault(base, {})["w"] = list(v)
        else:
            statics[k] = list(v)

    for base, pools in bases.items():
        if "start" not in pools or "w" not in pools:
            raise ValueError(f"Missing start/w pair for '{base}'")

    meta = {}
    for base, pools in bases.items():
        s_ids, s_map = _by_key(pools["start"], key_fn)
        w_ids, w_map = _by_key(pools["w"], key_fn)
        eq_ids = list(set(s_ids) & set(w_ids))
        meta[base] = {"s_ids": s_ids, "w_ids": w_ids, "s_map": s_map, "w_map": w_map, "eq_ids": eq_ids}

    names = list(bases.keys())

    stat_meta = {n: _by_key(v, key_fn) for n, v in statics.items()}
    static_names = list(stat_meta.keys())
    static_products = list(product(*(ids for ids, _ in stat_meta.values()))) if static_names else [()]

    for changer in names:
        non_changers = [n for n in names if n != changer]
        if any(len(meta[n]["eq_ids"]) == 0 for n in non_changers):
            continue

        for eq_choice_tuple in product(*(meta[n]["eq_ids"] for n in non_changers)):
            eq_choice = dict(zip(non_changers, eq_choice_tuple))

            for s_id in meta[changer]["s_ids"]:
                for w_id in meta[changer]["w_ids"]:
                    if s_id == w_id:
                        continue

                    for static_tuple in static_products:
                        combo = {}

                        # add all non-changers (same values)
                        for n in non_changers:
                            nid = eq_choice[n]
                            val = meta[n]["s_map"].get(nid, meta[n]["w_map"][nid])
                            combo[f"{n}{SUFFIX_START}"] = val
                            combo[f"{n}{SUFFIX_W}"] = val

                        # changer differs
                        combo[f"{changer}{SUFFIX_START}"] = meta[changer]["s_map"][s_id]
                        combo[f"{changer}{SUFFIX_W}"] = meta[changer]["w_map"][w_id]

                        # statics (same for both)
                        for name, sid in zip(static_names, static_tuple):
                            ids, by_id = stat_meta[name]
                            combo[name] = by_id[sid]

                        yield combo

def run():
    