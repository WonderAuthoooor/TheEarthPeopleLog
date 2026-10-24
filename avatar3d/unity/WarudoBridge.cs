// SDK bootstrap remains separate from the reusable FBX/Humanoid importer.
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace AvatarLab.Editor
{
    public static class WarudoBridge
    {
        static string Root { get { return Directory.GetParent(Application.dataPath).FullName; } }

        public static void ConfigureAndExit()
        {
            try
            {
                if (Application.unityVersion != "2021.3.45f2") throw new InvalidOperationException("Wrong editor version.");
                PlayerSettings.SetApiCompatibilityLevel(BuildTargetGroup.Standalone, ApiCompatibilityLevel.NET_4_6);
                PlayerSettings.assemblyVersionValidation = false;
                AssetDatabase.SaveAssets();
                File.WriteAllText(Path.Combine(Root, "AvatarBridge", "sdk-settings.txt"),
                    "editor=" + Application.unityVersion + "\napi=" + PlayerSettings.GetApiCompatibilityLevel(BuildTargetGroup.Standalone) +
                    "\nassemblyVersionValidation=" + PlayerSettings.assemblyVersionValidation + "\n");
                EditorApplication.Exit(0);
            }
            catch (Exception error) { Debug.LogException(error); EditorApplication.Exit(21); }
        }

        // Read installed public signatures before choosing a supported SDK build entry.
        public static void InspectAndExit()
        {
            try
            {
                var lines = AppDomain.CurrentDomain.GetAssemblies()
                    .Where(a => a.GetName().Name.StartsWith("UMod", StringComparison.Ordinal))
                    .SelectMany(a => a.GetExportedTypes())
                    .Where(t => t.FullName.Contains("ModToolsUtil") || t.FullName.Contains("ExportSettings") ||
                        t.Name.Contains("ModProject") || t.Name.Contains("CreateMod") || t.Name.Contains("BuildEngine"))
                    .OrderBy(t => t.FullName)
                    .SelectMany(t => new[] { "TYPE " + t.FullName }.Concat(
                        t.GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
                            .Select(m => "  " + m.MemberType + " " + m)));
                File.WriteAllLines(Path.Combine(Root, "AvatarBridge", "sdk-public-api.txt"), lines);
                EditorApplication.Exit(0);
            }
            catch (Exception error) { Debug.LogException(error); EditorApplication.Exit(22); }
        }
    }
}
