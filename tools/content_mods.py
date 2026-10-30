"""
Content mods applied in order by tools/build_content.py. Each mod takes the build Context and edits data files
(ctx.ace / ctx.raw_replace / ctx.strings) or art packages (ctx.package_file). Mods hold only our own changes.
"""

# Asset package -> directory under Local Store (server/server.py PACKAGE_PATHS, EExternalAsset.as:10-60)
PACKAGE_DIRS = {
    "shop": "asset/module/shop/",
}


def free_bam_pro(ctx):
    """BAM Pro popup price line (key bam_pro_price, EBamProLoc.as:18, BamProPopup.as:109)."""
    for lang, text in (("en", "FREE OF CHARGE!"), ("fr", "TOTALEMENT GRATUIT !")):
        ctx.set_text(lang, "bam_pro", "bam_pro_price", text)


MODS = [
    free_bam_pro,
]
