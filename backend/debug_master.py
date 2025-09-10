import sys
from pptx import Presentation
from pptx.enum.dml import MSO_FILL

def inspect_master(pptx_path):
    """
    Inspects the first slide master of a presentation for a background picture.
    """
    try:
        prs = Presentation(pptx_path)
        if not prs.slide_masters:
            print("No slide masters found in this presentation.")
            return

        master = prs.slide_masters[0]
        print("\n--- Inspecting Slide Master ---")

        # Check the primary background of the master itself
        if master.background.fill.type == MSO_FILL.PICTURE:
            print("✅ FOUND: The slide master's primary background is a picture.")
        else:
            print("❌ NOT FOUND: The slide master's primary background is NOT a picture.")
            
        # Also check if any shapes on the master have a picture FILL
        for shape in master.shapes:
            if shape.fill.type == MSO_FILL.PICTURE:
                print(f"✅ FOUND: A shape named '{shape.name}' on the master has a picture background fill.")
                
        print("\n--- Inspection Complete ---")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_master.py <path_to_pptx_file>")
    else:
        inspect_master(sys.argv[1])