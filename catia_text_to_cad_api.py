"""
CATIA 3DExperience V6 Agentic CAD Interface
-------------------------------------------
This script enables natural language control of CATIA V6 geometry creation using the DeepSeek API.
It connects to a running CATIA session via COM and acts as an "Engineering Agent".

PREREQUISITES:
1. CATIA 3DExperience (V6) must be running.
2. Python 3.x installed.
3. Libraries: 
   - `pip install pywin32 requests`
   - `win32com.client` must be able to dispatch "CATIA.Application".
4. DeepSeek API Key:
   - You must have a valid API Key from https://platform.deepseek.com/
   - Replace "YOUR_API_KEY_HERE" below.

USAGE:
Run the script in a terminal: `python catia_text_to_cad_api.py`
Type natural language commands like:
- "Create only a point at 10,20,30"
- "Create a cylinder radius 50 thickness 20 on XY plane"

Author: [Your Name / Organization]
"""

import win32com.client
import requests
import json
import re
import sys
import traceback

# --- CONFIG ---
# ⚠️ REPLACE WITH YOUR OWN API KEY
API_KEY = "YOUR_API_KEY_HERE"  
API_URL = "https://api.deepseek.com/chat/completions"

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """You are an expert CATIA V6 Automation Engineer using Python and pywin32.
Your task is to generate executable Python code to create geometry (Wireframe OR Solids) in CATIA.

CONTEXT:
- The script PRE-DEFINES these variables for you:
  - `catia`: The application object
  - `editor`: Active editor
  - `part`: Active part
  - `hsf`: HybridShapeFactory
  - `sf`: ShapeFactory
  - `bodies`: Part.Bodies
  - `selection`: Editor.Selection

RULES:
1. Output ONLY valid Python code inside ```python``` blocks.
2. NO NEED to redefine `part`, `hsf`, etc. They are available.
3. For SOLIDS (Pads/Pockets), you MUST create a Sketch first.
3. ALWAYS use `Reference` objects for inputs. `part.CreateReferenceFromObject(obj)`
4. For Sketches: 
   - Get `part.MainBody` or a Body.
   - `sk = body.Sketches.Add(ref_plane)`
   - `o2D = sk.OpenEdition()`, create geometry, `sk.CloseEdition()`.

SAFE RETRIEVAL RULE:
- **USE HELPERS** provided by the script:
  - `hb = require_geoset(part, "AI_Generated")`
  - `body = require_body(part, "PartBody")`
- DO NOT use `Item("...")` manually.

SOLID STACKING RULE (The "Golden Rule" for Pads):
- When creating a solid on top of another solid:
  - **DO NOT** create offset planes for the sketch support. (AddNewPad fails on datum planes).
  - **ALWAYS** use the PLANAR FACE of the existing solid.
  - **PATTERN:**
    ```python
    # 1. Get reference to the face (e.g. XY plane OR Top Face of previous Pad)
    ref_face = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
    
    # 2. Sketch on that face
    sk = body.Sketches.Add(ref_face)
    ...draw...
    part.Update()
    
    # 3. Create Pad
    pad = sf.AddNewPad(sk, 20.0)
    part.Update()
    ```
- **CRITICAL:** Before creating any SOLID feature (Pad), ensure:
  - `part.InWorkObject = body`
  - `part.Update()`

HELPER: `get_top_face(pad)` will be injected to help you.
- It prints debug info. CHECK IT.

TRICK FOR SOLIDS (The "Flange" pattern):
```python
# CRITICAL: Use MainBody (guaranteed to exist)
body = part.MainBody
part.InWorkObject = body

# Base Pad
ref_xy = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
sk1 = body.Sketches.Add(ref_xy)

f2d = sk1.Factory2D
sk1.OpenEdition()
f2d.CreateClosedCircle(0.0, 0.0, 50.0)
sk1.CloseEdition()
part.Update()

pad1 = sf.AddNewPad(sk1, 20.0)
part.Update() # Ensure Pad1 exists

# Stack on top
ref_top = get_top_face(pad1) 
sk2 = body.Sketches.Add(ref_top)

f2d2 = sk2.Factory2D
sk2.OpenEdition()
f2d2.CreateClosedCircle(0.0, 0.0, 30.0)
sk2.CloseEdition()
part.Update()

pad2 = sf.AddNewPad(sk2, 10.0)
# CRITICAL: Fix Direction for Stacked Pads
# 0 = Regular (Into the base), 1 = Opposite (Out/Up)
# If it goes into the part, set to 1.
pad2.DirectionOrientation = 1 
part.Update()
```

DIRECTION RULE FOR STACKED PADS:
- When creating a Pad on top of another solid, the default direction is often INWARDS.
- **ALWAYS** set `pad.DirectionOrientation = 1` (Opposite) to force it outwards/upwards.
- `pad.ReverseDirection` is NOT valid. Use `DirectionOrientation`.

When user asks for "Holes", simplify by using `sf.AddNewHoleFromPoint(x,y,z, ref_plane, depth)` if possible, OR Sketch+Pocket.
"""

def call_deepseek_for_code(user_prompt):
    print("   🧠 Thinking (DeepSeek)...")
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1 # Keep it deterministic for code
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            return content
        else:
            print(f"❌ API Error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
    return None

def extract_python_code(text):
    match = re.search(r"```python(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: maybe the whole text is code
    if "hsf =" in text or "catia." in text:
        return text
    return None


# --- HELPER FUNCTIONS FOR AI (Injected) ---
def require_geoset(part, name):
    try:
        return part.HybridBodies.Item(name)
    except:
        hb = part.HybridBodies.Add()
        hb.Name = name
        return hb

def require_body(part, name):
    try:
        return part.Bodies.Item(name)
    except:
        body = part.Bodies.Add()
        body.Name = name
        return body

def get_top_face(pad):
    try:
        # Need to access the Selection object safely. 
        # In V6, it is on the ActiveEditor.
        # Since 'catia' object might not be passed here, we grab it or use the global one if possible.
        # Safest way: Grab active object.
        catia = win32com.client.GetActiveObject("CATIA.Application")
        sel = catia.ActiveEditor.Selection
        
        part = pad.Parent.Parent
        sel.Clear()
        sel.Add(pad)
        sel.Search("Topology.Face.Planar,sel")
        print(f"   (Debug: Found {sel.Count} planar faces on pad)")
        
        if sel.Count > 0:
            # Return the last face (heuristic for Top)
            ref = part.CreateReferenceFromObject(sel.Item(sel.Count).Value)
            return ref
    except Exception as e:
        print(f"   (Debug: get_top_face error: {e})")
    return None

def main():
    print("="*50)
    print("CATIA GENERATIVE AGENT (Text-to-Geometry)")
    print("="*50)
    print("Initializing CATIA connection...")
    
    try:
        catia = win32com.client.GetActiveObject("CATIA.Application")
        print("Connected to CATIA V6")
    except:
        print("Could not connect to CATIA (Is it running?)")
        # Ensure user knows why it failed
        print("\n[!] Check that CATIA 3DExperience is running and a Part is active.")
        return

    while True:
        print("\n" + "-"*30)
        user_input = input("Enter Command (or 'q' to quit): ")
        if user_input.lower() in ['q', 'exit']:
            break
            
        if API_KEY == "YOUR_API_KEY_HERE":
            print("❌ ERROR: Please edit the script and insert your valid DeepSeek API Key!")
            continue

        # 1. GENERATE
        raw_response = call_deepseek_for_code(user_input)
        if not raw_response: continue
        
        code = extract_python_code(raw_response)
        
        if not code:
            print("⚠️ No valid code found in AI response.")
            print(f"Raw: {raw_response}")
            continue
            
        print("\nGENERATED CODE:")
        print("\033[96m" + code + "\033[0m") 
        
        # 2. VALIDATE 
        confirm = input("\nExecute this? (y/n): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            continue
            
        # 3. EXECUTE
        print("Executing...")
        try:
            # PRE-INJECT COMMON OBJECTS
            editor = catia.ActiveEditor
            active_obj = editor.ActiveObject
            
            # Robust Part Detection:
            real_part = active_obj
            try:
                _ = real_part.HybridShapeFactory
            except:
                print("   (ActiveObject is not a Part, searching for 3D Part context...)")
                try:
                    sel = editor.Selection
                    sel.Clear()
                    sel.Search("CATGmoSearch.Part,all")
                    if sel.Count > 0:
                        real_part = sel.Item(1).Value
                        print(f"   (Found Part: {real_part.Name})")
                except:
                    pass

            exec_globals = {
                "win32com": win32com,
                "catia": catia,
                "editor": editor,
                "part": real_part,
                "selection": editor.Selection,
                # Inject Helpers
                "require_geoset": require_geoset,
                "require_body": require_body,
                "get_top_face": get_top_face
            }

            # Safe injection of factories
            try: exec_globals["hsf"] = real_part.HybridShapeFactory
            except: pass
            
            try: exec_globals["sf"] = real_part.ShapeFactory
            except: pass
            
            try: exec_globals["bodies"] = real_part.Bodies
            except: pass
            
            exec(code, exec_globals)
            print("Success!")
            
        except Exception as e:
            print("Execution Failed:")
            traceback.print_exc()

if __name__ == "__main__":
    main()
