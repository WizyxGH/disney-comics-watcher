import os
from src.dbi.utils import _format_date_for_dbi, _format_price_for_dbi, sort_dbi_file
from src.dbi.mappers import (
    resolve_magazine_metadata, resolve_us_metadata, resolve_de_metadata, 
    resolve_gr_metadata, resolve_glenat_metadata, resolve_it_metadata, resolve_br_metadata,
    resolve_eg_metadata, resolve_bg_metadata, resolve_hr_metadata, resolve_ee_metadata, resolve_lv_metadata, resolve_lt_metadata, resolve_pl_metadata, resolve_cz_metadata, resolve_rs_metadata, resolve_si_metadata, resolve_cn_metadata, resolve_dk_metadata, resolve_es_metadata, resolve_fi_metadata, resolve_is_metadata, resolve_no_metadata, resolve_nl_metadata, resolve_uk_metadata, resolve_se_metadata
)

_RESOLVERS = {
    "us":       resolve_us_metadata,
    "de":       resolve_de_metadata,
    "gr":       resolve_gr_metadata,
    "it":       resolve_it_metadata,
    "br":       resolve_br_metadata,
    "eg":       resolve_eg_metadata,
    "bg":       resolve_bg_metadata,
    "hr":       resolve_hr_metadata,
    "ee":       resolve_ee_metadata,
    "lv":       resolve_lv_metadata,
    "lt":       resolve_lt_metadata,
    "pl":       resolve_pl_metadata,
    "cz":       resolve_cz_metadata,
    "rs":       resolve_rs_metadata,
    "si":       resolve_si_metadata,
    "cn":       resolve_cn_metadata,
    "dk":       resolve_dk_metadata,
    "es":       resolve_es_metadata,
    "fi":       resolve_fi_metadata,
    "is":       resolve_is_metadata,
    "no":       resolve_no_metadata,
    "nl":       resolve_nl_metadata,
    "uk":       resolve_uk_metadata,
    "se":       resolve_se_metadata,
    "glenat":   resolve_glenat_metadata,
    # magazine needs overrides -> handled separately
}

def generate_dbi_skeleton(info: dict, publication_type: str, overrides: dict | None = None) -> str | None:
    overrides = overrides or {}
    try:
        if publication_type == "magazine":
            data = resolve_magazine_metadata(info, overrides)
        else:
            resolver = _RESOLVERS.get(publication_type, resolve_glenat_metadata)
            data = resolver(info)

        issue_path = data["issue_path"]
        
        if publication_type == "de":
            try:
                from src.ltb_enricher import enrich_ltb_metadata
                info["issue_path"] = issue_path
                info = enrich_ltb_metadata(info)
                if info.get("name"):
                    data["name"] = info["name"]
                if info.get("date"):
                    data["date"] = info["date"]
                if info.get("pages"):
                    data["pages"] = info["pages"]
            except Exception as e:
                print(f"  [warn] Failed to enrich LTB: {e}")
                
        name = data["name"]
        prix_raw = data["price"]
        date_raw = data["date"]
        pages_val = data["pages"]
        size_val = data["size"]
        isstrans = data["isstrans"]
        ean_val = data["ean"]

        issdate = _format_date_for_dbi(date_raw)
        price   = _format_price_for_dbi(prix_raw)

        os.makedirs("issues", exist_ok=True)
        dbi_path = os.path.join("issues", f"{publication_type}.dbi" if publication_type in ["us", "de", "gr", "it", "br", "eg", "bg", "hr", "ee", "lv", "lt", "pl", "cz", "rs", "si", "cn", "dk", "es", "fi", "is", "no", "nl", "uk", "se"] else "fr.dbi")

        dbi_issue_code = issue_path
        for prefix in ("fr/", "us/", "de/", "gr/", "it/", "br/", "eg/", "bg/", "hr/", "ee/", "lv/", "lt/", "pl/", "cz/", "rs/", "si/", "cn/", "dk/", "es/", "fi/", "is/", "no/", "nl/", "uk/", "se/"):
            if dbi_issue_code.startswith(prefix):
                dbi_issue_code = dbi_issue_code[3:]
                break

        isslet_val = None
        if dbi_issue_code.startswith("JM "):
            if not pages_val: pages_val = 116
            isslet_val = "B.L.A.C.K Studio"

        if len(dbi_issue_code) <= 12:
            issue_code_field = dbi_issue_code.ljust(12)
        else:
            issue_code_field = "->" + " " * 10 

        fields = []
        if issdate: fields.append(f"[issdate:{issdate}]")
        if price: fields.append(f"[price:{price}]")
        if pages_val: fields.append(f"[pages:{pages_val}]")
        if size_val: fields.append(f"[size:{size_val}]")
        if ean_val: fields.append(f"[EAN {ean_val}]")
        if isstrans: fields.append(f"[isstrans:{isstrans}]")
        
        if info.get("stories"):
            fields.append("[inx:FGK,-]")
        else:
            fields.append("[inx:-]")

        fields_str = " ".join(fields)
        title_part = f"{name} {fields_str}".strip()

        h3_line = f"{issue_code_field} h3 {title_part}\n"

        cover_ec = dbi_issue_code + "a"
        storycode = "?"
        
        storycode_field = storycode[:14].ljust(14)
        pages_field     = " " + "1".rjust(4)
        brokpg          = " "
        pagel           = "c "
        
        plot_val, writ_val, art_val, ink_val, hero_val = "", "", "", "", ""

        for c in info.get("characters", []):
            if c.get("code"):
                hero_val = c["code"]
                break

        if dbi_issue_code.startswith("JM "):
            writ_val, art_val = "FPt", "FPt"

        rest = plot_val.ljust(4) + writ_val.ljust(4) + art_val.ljust(4) + ink_val.ljust(4) + hero_val.ljust(1)
        rest = rest[:17].ljust(17)

        if len(cover_ec) <= 12:
            prefix = f"{cover_ec.ljust(12)}{storycode_field}{pages_field}{brokpg}{pagel}{rest}"
        else:
            prefix = f"->          {storycode_field}{pages_field}{brokpg}{pagel}{rest}"

        cover_title = info.get("cover_title") or ""
        suffixes = []
        if cover_title: suffixes.append(cover_title)
        if len(cover_ec) > 12: suffixes.append(f"[entrycode:{cover_ec}]")
        
        characters = info.get("characters", [])
        if characters:
            xapp_codes = [c["code"] for c in characters if c.get("code")]
            if xapp_codes:
                suffixes.append(f"[xapp:{','.join(xapp_codes)}]")
                
        if isslet_val: suffixes.append(f"[isslet:{isslet_val}]")

        suffix_str = " ".join(suffixes)
        # No extra spaces between prefix and suffix_str
        cover_line = f"{prefix}{suffix_str}".rstrip() + "\n"
        
        body_parts = []
        
        src_url = info.get("url") or info.get("link") or ""
        if src_url:
            body_parts.append(f"\n^^ Source: {src_url}\n")
        else:
            body_parts.append(f"\n^^ Source:\n")
            
        body_parts.append(h3_line)
        body_parts.append(cover_line)

        stories = info.get("stories", [])
        if stories:
            total_pages = 0
            if pages_val:
                try: total_pages = int(str(pages_val).strip())
                except: pass

            current_page = 5 if "LTB " in dbi_issue_code else 1

            for i, story in enumerate(stories, start=1):
                page_len_str = str(story.get("pages", "")).strip()
                if page_len_str.isdigit():
                    if total_pages >= 100:
                        story_ec = f"{dbi_issue_code}p{str(current_page).zfill(3)}"
                    else:
                        story_ec = f"{dbi_issue_code}p{str(current_page).zfill(2)}"
                    current_page += int(page_len_str)
                else:
                    story_ec = f"{dbi_issue_code}{chr(97 + i)}"
                
                story_code = story.get("story_code", "") or story.get("code", "")
                
                pages_str = str(story.get("pages", "")).strip()
                st_pages_block = " " + pages_str.rjust(4)
                    
                brokpg = " "
                pagel = "  "
                
                story_rest = " " * 17
                
                if len(story_ec) <= 12:
                    st_prefix = f"{story_ec.ljust(12)}{story_code.ljust(14)}{st_pages_block}{brokpg}{pagel}{story_rest}"
                else:
                    st_prefix = f"->          {story_code.ljust(14)}{st_pages_block}{brokpg}{pagel}{story_rest}"

                st_title = story.get("title", "").strip()
                st_suffixes = []
                if "LTB " in dbi_issue_code:
                    st_suffixes.append("[part:]")
                if len(story_ec) > 12: st_suffixes.append(f"[entrycode:{story_ec}]")
                if story.get("characters"):
                    c_codes = [c["code"] for c in story["characters"] if c.get("code")]
                    if c_codes: st_suffixes.append(f"[xapp:{','.join(c_codes)}]")

                st_suffix_str = " ".join(st_suffixes)
                # No extra spaces between st_prefix and st_title
                st_line = f"{st_prefix}{st_title} {st_suffix_str}".rstrip() + "\n"
                body_parts.append(st_line)

        content = "".join(body_parts)
        with open(dbi_path, "a", encoding="utf-8") as f:
            f.write(content)
        print(f"  [DBI] Entry added to {dbi_path} ({issue_path})")
        sort_dbi_file(dbi_path)
        return content

    except Exception as e:
        print(f"  [warn] Unable to generate DBI skeleton: {e}")
        return None
