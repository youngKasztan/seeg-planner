// SeegMaterials.cs (Editor only) - creates the two URP Lit materials that PatientLoader puts on the model:
//   Assets/SeegPlanner/Resources/SeegLitOpaque.mat        solid layers, robot paths, targets
//   Assets/SeegPlanner/Resources/SeegLitTransparent.mat   faint layers (brain, skull, skin)
// They live in a Resources folder, so they (and their shader variants) are always in the player build.
// Without them the headset app shows the model pink: glTFast's own shaders are stripped from builds.
// Created automatically when the project opens; menu Tools > SEEG Planner > Recreate headset materials rebuilds them.
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace SeegPlanner.EditorTools
{
    [InitializeOnLoad]
    static class SeegMaterials
    {
        const string Parent = "Assets/SeegPlanner";
        const string Dir = Parent + "/Resources";

        static SeegMaterials() { EditorApplication.delayCall += () => Create(false); }

        [MenuItem("Tools/SEEG Planner/Recreate headset materials")]
        static void Recreate() { Create(true); }

        static void Create(bool force)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) { Debug.LogWarning("URP Lit shader not found - is URP the active render pipeline?"); return; }
            if (!AssetDatabase.IsValidFolder(Parent)) return;
            if (!AssetDatabase.IsValidFolder(Dir)) AssetDatabase.CreateFolder(Parent, "Resources");
            bool made = Make(Dir + "/SeegLitOpaque.mat", shader, false, force);
            made |= Make(Dir + "/SeegLitTransparent.mat", shader, true, force);
            if (made) { AssetDatabase.SaveAssets(); AssetDatabase.Refresh(); }
        }

        static bool Make(string path, Shader shader, bool transparent, bool force)
        {
            if (AssetDatabase.LoadAssetAtPath<Material>(path) != null)
            {
                if (!force) return false;
                AssetDatabase.DeleteAsset(path);
            }
            var m = new Material(shader);
            m.SetFloat("_Metallic", 0f);
            m.SetFloat("_Smoothness", 0.35f);
            m.SetFloat("_Cull", (float)CullMode.Off);                     // double sided, like the glTF materials
            if (transparent)
            {
                m.SetFloat("_Surface", 1f);                                 // Transparent
                m.SetFloat("_Blend", 0f);                                   // Alpha
                m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
                m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
                m.SetFloat("_SrcBlendAlpha", (float)BlendMode.One);         // keeps passthrough blending correct
                m.SetFloat("_DstBlendAlpha", (float)BlendMode.OneMinusSrcAlpha);
                m.SetFloat("_ZWrite", 0f);
                m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                m.SetOverrideTag("RenderType", "Transparent");
                m.renderQueue = (int)RenderQueue.Transparent;
                m.SetShaderPassEnabled("DepthOnly", false);
                m.SetShaderPassEnabled("ShadowCaster", false);
                m.SetColor("_BaseColor", new Color(1f, 1f, 1f, 0.2f));
            }
            else m.SetColor("_BaseColor", Color.white);
            AssetDatabase.CreateAsset(m, path);
            Debug.Log("SEEG Planner: created " + path);
            return true;
        }
    }
}
