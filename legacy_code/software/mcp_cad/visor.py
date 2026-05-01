import matplotlib.pyplot as plt
import ezdxf
import sys

def renderizar_dxf_a_png(dxf_path, png_path):
    print(f"Renderizando visor para: {dxf_path}...")
    try:
        # Importaci├│n de m├│dulos drawing
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        import ezdxf.addons.drawing.config as config
        
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        fig = plt.figure(figsize=(4, 4))
        ax = fig.add_axes([0, 0, 1, 1])
        
        ctx = RenderContext(doc)
        
        cfg = config.Configuration(
            background_policy=config.BackgroundPolicy.CUSTOM,
            custom_bg_color="#ffffff",
            color_policy=config.ColorPolicy.CUSTOM,
            custom_fg_color="#000000",
        )
        out = MatplotlibBackend(ax)
        Frontend(ctx, out, config=cfg).draw_layout(msp, finalize=True)
        
        ax.set_aspect('equal', adjustable='datalim')
        ax.autoscale()
        ax.axis('off')
        
        fig.savefig(png_path, dpi=72, bbox_inches='tight')
        plt.close(fig)
        print(f"┬íRender gr├ífico completado en {png_path}!")
    except Exception as e:
        print(f"Error renderizando el entorno gr├ífico: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python visor.py <archivo.dxf> <salida.png>")
    else:
        renderizar_dxf_a_png(sys.argv[1], sys.argv[2])
