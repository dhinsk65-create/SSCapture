"""アイコン生成スクリプト（ビルド時に実行）"""
from PIL import Image, ImageDraw

def make_camera_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    m = s * 0.06  # margin

    # 背景を角丸っぽく
    bg_color = "#2d7dd2"
    d.rounded_rectangle([m, m, s-m, s-m], radius=s*0.18, fill=bg_color)

    # カメラボディ
    bx0, by0 = s*0.12, s*0.30
    bx1, by1 = s*0.88, s*0.82
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=s*0.08, fill="white")

    # レンズ外枠
    cx, cy, cr = s*0.50, s*0.56, s*0.18
    d.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], fill="#2d7dd2")

    # レンズ内
    ir = cr * 0.65
    d.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], fill="white")

    # レンズ中心
    pr = ir * 0.45
    d.ellipse([cx-pr, cy-pr, cx+pr, cy+pr], fill="#2d7dd2")

    # ファインダー（上部の小さな四角）
    fx0, fy0 = s*0.32, s*0.20
    fx1, fy1 = s*0.54, s*0.32
    d.rounded_rectangle([fx0, fy0, fx1, fy1], radius=s*0.04, fill="white")

    # フラッシュ部分（右上の小円）
    d.ellipse([s*0.68, s*0.20, s*0.80, s*0.32], fill="white")

    return img


def create_ico(path: str):
    sizes = [256, 128, 64, 48, 32, 16]
    images = [make_camera_icon(s) for s in sizes]
    images[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Created: {path}")


if __name__ == "__main__":
    create_ico("icon.ico")
