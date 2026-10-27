// Standalone editor helper. No Warudo dependency; SDK packaging is a later step.
using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

namespace AvatarLab.Editor
{
    public static class AvatarBridge
    {
        [Serializable] public class Binding { public string humanBone; public string sourceBone; }
        [Serializable] public class Request
        {
            public int schema; public string editorVersion; public string fbxAsset; public string fbxSha256;
            public int fps; public int frames; public float duration; public bool loop;
            public string modelSha256; public string actionId; public Binding[] bindings;
        }
        [Serializable] public class Report
        {
            public int schema = 1;
            public string runId; public string time; public string editorVersion; public string fbxSha256;
            public string modelSha256; public bool passed; public string stage;
            public string clipAsset; public string clipSha256; public float expectedDuration;
            public float actualDuration; public float frameRate; public int mappedBones;
            public string actionId; public bool loop; public float loopMaxCurveError;
            public string error; public string warudoPlayback = "pending";
        }
        const string Version = "2021.3.45f2";
        const string Input = "Assets/AvatarBridge/Input/animation.fbx";

        [MenuItem("Avatar Bridge/Validate and Extract Animation")]
        public static void RunMenu()
        {
            try { Run(); }
            catch (Exception error) { Debug.LogException(error); }
        }

        public static void RunBatch()
        {
            try { Run(); EditorApplication.Exit(0); }
            catch (Exception error) { Debug.LogException(error); EditorApplication.Exit(20); }
        }

        static void Require(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
        }

        static string Hash(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }

        static void Run()
        {
            var root = Directory.GetParent(Application.dataPath).FullName;
            var id = DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffZ") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8);
            var folder = Path.Combine(root, "AvatarBridge", "Runs", id);
            Directory.CreateDirectory(folder);
            var report = new Report { runId = id, time = DateTimeOffset.Now.ToString("o"),
                editorVersion = Application.unityVersion, stage = "validating" };
            try
            {
                Require(Application.unityVersion == Version, "This project requires Unity " + Version);
                var request = JsonUtility.FromJson<Request>(File.ReadAllText(Path.Combine(root, "AvatarBridge", "request.json")));
                Require(request != null && request.schema == 1 && request.editorVersion == Version && request.fbxAsset == Input,
                    "Invalid bridge request or FBX path.");
                Require(request.fps > 0 && request.fps <= 120 && request.frames >= 2 && request.frames <= 21601 &&
                    !float.IsNaN(request.duration) && !float.IsInfinity(request.duration) &&
                    Math.Abs(request.duration - (request.frames - 1f) / request.fps) < 0.00001f, "Invalid source timing.");
                report.fbxSha256 = Hash(Path.Combine(root, Input));
                report.modelSha256 = request.modelSha256;
                report.actionId = string.IsNullOrEmpty(request.actionId) ? "wave" : request.actionId;
                Require(new[] { "neutral", "idle", "explain", "bend", "wave", "hold", "turntable" }.Contains(report.actionId),
                    "Unknown action ID.");
                report.loop = request.loop;
                Require(report.fbxSha256 == request.fbxSha256, "FBX checksum mismatch.");
                report.expectedDuration = request.duration;
                AssetDatabase.ImportAsset(Input, ImportAssetOptions.ForceSynchronousImport);
                var importer = AssetImporter.GetAtPath(Input) as ModelImporter;
                Require(importer != null, "FBX importer not available.");
                importer.animationType = ModelImporterAnimationType.Human;
                importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                importer.importAnimation = true;
                importer.animationCompression = ModelImporterAnimationCompression.Off;
                importer.SaveAndReimport();

                var model = AssetDatabase.LoadAssetAtPath<GameObject>(Input);
                Require(model != null, "FBX model import failed.");
                var transforms = model.GetComponentsInChildren<Transform>(true);
                var description = importer.humanDescription;
                Require(description.skeleton != null && description.skeleton.Length > 0, "Imported skeleton is empty.");
                Require(request.bindings != null && request.bindings.Length >= 15, "Required bone mappings missing.");
                var bones = request.bindings.Select(binding =>
                {
                    Require(binding != null && !string.IsNullOrEmpty(binding.sourceBone), "Empty bone binding.");
                    HumanBodyBones bone;
                    Require(Enum.TryParse(binding.humanBone, out bone) && bone >= 0 && bone < HumanBodyBones.LastBone,
                        "Unknown human bone: " + binding.humanBone);
                    Require(transforms.Count(t => t.name == binding.sourceBone) == 1,
                        "Source bone missing or ambiguous: " + binding.sourceBone);
                    return new HumanBone { boneName = binding.sourceBone,
                        humanName = HumanTrait.BoneName[(int)bone], limit = new HumanLimit { useDefaultValues = true } };
                }).ToArray();
                Require(bones.Select(b => b.boneName).Distinct().Count() == bones.Length &&
                    bones.Select(b => b.humanName).Distinct().Count() == bones.Length, "Duplicate humanoid mapping.");
                for (var i = 0; i < HumanTrait.BoneCount; i++)
                    Require(!HumanTrait.RequiredBone(i) || bones.Any(b => b.humanName == HumanTrait.BoneName[i]),
                        "Required humanoid bone missing: " + HumanTrait.BoneName[i]);
                description.human = bones;
                importer.humanDescription = description;
                importer.SaveAndReimport();
                var avatar = AssetDatabase.LoadAllAssetsAtPath(Input).OfType<Avatar>().SingleOrDefault();
                Require(avatar != null && avatar.isValid && avatar.isHuman, "Unity humanoid Avatar is invalid; inspect Rig mapping/T-pose.");
                var clips = AssetDatabase.LoadAllAssetsAtPath(Input).OfType<AnimationClip>()
                    .Where(c => !c.name.StartsWith("__preview__", StringComparison.Ordinal)).ToArray();
                Require(clips.Length == 1, "Expected exactly one animation take; do not silently select a different clip.");
                var clip = clips[0];
                Require(clip.isHumanMotion && !clip.legacy, "Clip is not a humanoid animation.");
                report.actualDuration = clip.length; report.frameRate = clip.frameRate; report.mappedBones = bones.Length;
                Require(Math.Abs(clip.length - request.duration) < 0.001f && Math.Abs(clip.frameRate - request.fps) < 0.01f,
                    "Animation timing changed; no automatic stretching allowed.");
                // Each run has its own clip/report. Previous results and user assets are never overwritten.
                var outputFolder = "Assets/AvatarBridge/Runs/" + id;
                Directory.CreateDirectory(Path.Combine(root, outputFolder));
                AssetDatabase.Refresh();
                report.clipAsset = outputFolder + "/Animation.anim";
                var copy = UnityEngine.Object.Instantiate(clip);
                copy.name = "Animation";
                var settings = AnimationUtility.GetAnimationClipSettings(copy);
                settings.loopTime = request.loop;
                AnimationUtility.SetAnimationClipSettings(copy, settings);
                AssetDatabase.CreateAsset(copy, report.clipAsset);
                AssetDatabase.SaveAssets();
                var saved = AssetDatabase.LoadAssetAtPath<AnimationClip>(report.clipAsset);
                Require(saved != null && saved.isHumanMotion && Math.Abs(saved.length - request.duration) < 0.001f,
                    "Saved animation validation failed.");
                Require(AnimationUtility.GetAnimationClipSettings(saved).loopTime == request.loop,
                    "Saved loop setting changed.");
                if (request.loop)
                {
                    foreach (var binding in AnimationUtility.GetCurveBindings(saved))
                    {
                        var curve = AnimationUtility.GetEditorCurve(saved, binding);
                        report.loopMaxCurveError = Math.Max(report.loopMaxCurveError,
                            Math.Abs(curve.Evaluate(0) - curve.Evaluate(saved.length)));
                    }
                    Require(report.loopMaxCurveError < 0.001f, "Humanoid loop endpoints are not closed.");
                }
                report.clipSha256 = Hash(Path.Combine(root, report.clipAsset));
                report.stage = "unity_humanoid_extracted";
                report.passed = true;
                Debug.Log("Avatar Bridge succeeded: " + report.clipAsset + "; Warudo playback still pending.");
            }
            catch (Exception error)
            {
                report.passed = false; report.stage = "failed"; report.error = error.ToString(); throw;
            }
            finally
            {
                var target = Path.Combine(folder, "report.json");
                File.WriteAllText(target + ".tmp", JsonUtility.ToJson(report, true));
                File.Move(target + ".tmp", target);
                Debug.Log("Avatar Bridge report: " + target);
            }
        }
    }
}
