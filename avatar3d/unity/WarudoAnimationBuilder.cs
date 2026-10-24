// Installed only after the pinned SDK is staged. Uses verified public UMod entry points.
using System;
using System.IO;
using System.Security.Cryptography;
using UMod.BuildEngine;
using UMod.ModTools.Export;
using UMod.Shared;
using UnityEditor;
using UnityEngine;

namespace AvatarLab.Editor
{
    public static class WarudoAnimationBuilder
    {
        [Serializable] class Request
        {
            public string sourceReport; public string reportSha256; public string clipSha256;
        }
        [Serializable] class ImportReport
        {
            public bool passed; public string editorVersion; public string clipAsset; public string clipSha256;
        }
        [Serializable] class Result
        {
            public int schema = 1; public string runId; public bool passed; public string error;
            public string clipSha256; public string modName; public string modFile; public string modSha256;
            public string editorVersion; public string warudoPlayback = "pending";
        }
        static string Hash(string path)
        {
            using (var input = File.OpenRead(path))
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
        }
        static void Require(bool condition, string message)
        { if (!condition) throw new InvalidOperationException(message); }

        public static void BuildAndExit()
        {
            var root = Directory.GetParent(Application.dataPath).FullName;
            var id = DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffZ") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8);
            var output = Path.Combine(root, "AvatarBridge", "Builds", id);
            Directory.CreateDirectory(output);
            var result = new Result { runId = id, editorVersion = Application.unityVersion };
            int exit = 23;
            try
            {
                Require(Application.unityVersion == "2021.3.45f2", "Wrong editor version.");
                var request = JsonUtility.FromJson<Request>(File.ReadAllText(Path.Combine(root, "AvatarBridge", "build-request.json")));
                var sourceReport = Path.GetFullPath(Path.Combine(root, request.sourceReport));
                Require(sourceReport.StartsWith(Path.Combine(root, "AvatarBridge", "Runs") + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase), "Import report outside expected Runs folder.");
                Require(Hash(sourceReport) == request.reportSha256, "Import report checksum mismatch.");
                var imported = JsonUtility.FromJson<ImportReport>(File.ReadAllText(sourceReport));
                Require(imported.passed && imported.editorVersion == Application.unityVersion &&
                    imported.clipSha256 == request.clipSha256, "Import is not verified.");
                var clipPath = Path.GetFullPath(Path.Combine(root, imported.clipAsset));
                Require(clipPath.StartsWith(Path.Combine(root, "Assets", "AvatarBridge", "Runs") + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase) && Hash(clipPath) == request.clipSha256, "Clip checksum or location mismatch.");
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(imported.clipAsset);
                Require(clip != null && clip.isHumanMotion && !clip.legacy, "Source clip is not humanoid.");
                result.clipSha256 = request.clipSha256;
                result.modName = "AvatarLabWave" + request.clipSha256.Substring(0, 12);
                var folder = "Assets/AvatarBridge/Mods/" + id;
                Directory.CreateDirectory(Path.Combine(root, folder));
                AssetDatabase.Refresh();
                Require(AssetDatabase.CopyAsset(imported.clipAsset, folder + "/Animation.anim"), "Failed to copy animation into mod.");
                var settings = ExportSettings.Active.LoadOrCreate("Assets/AvatarBridge");
                Require(settings != null, "Export settings could not be created.");
                var profile = settings.CreateNewExportProfile(true);
                profile.ModName = result.modName;
                profile.ModAuthor = "AvatarLab";
                profile.ModVersion = "0.1.0";
                profile.ModDescription = "Technical skeletal wave; runtime playback and visual acceptance pending.";
                profile.ModAssetsPath = folder;
                profile.ModExportPath = output;
                settings.ShowOutputDirectory = false;
                EditorUtility.SetDirty(settings);
                settings.Save();
                AssetDatabase.SaveAssets();
                Require(settings.ValidateRequiredValues(), "SDK rejected export settings.");
                var built = ModToolsUtil.StartBuild(settings, null);
                Require(built != null && built.Successful, built == null ? "No build result." : built.ErrorMessage);
                Require(built.BuiltModFile != null && built.BuiltModFile.Exists, "Built mod file missing.");
                result.modFile = built.BuiltModFile.FullName;
                Require(Path.GetFullPath(result.modFile).StartsWith(output + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase), "SDK output outside this run.");
                Require(built.BuiltModFile.Length > 0 && built.BuiltModFile.Extension == ".warudo", "Unexpected mod output.");
                result.modSha256 = Hash(result.modFile);
                result.passed = true;
                exit = 0;
            }
            catch (Exception error) { result.error = error.ToString(); Debug.LogException(error); }
            finally
            {
                File.WriteAllText(Path.Combine(output, "report.json.tmp"), JsonUtility.ToJson(result, true));
                File.Move(Path.Combine(output, "report.json.tmp"), Path.Combine(output, "report.json"));
                Debug.Log("Warudo build report: " + Path.Combine(output, "report.json"));
            }
            EditorApplication.Exit(exit);
        }
    }
}
