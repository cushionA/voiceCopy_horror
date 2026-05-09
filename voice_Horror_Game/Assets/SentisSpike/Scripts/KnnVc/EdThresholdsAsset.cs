// EdThresholdsAsset.cs — Phase 7 Group E
// voice_horror Phase 7 (2026-05-09)
//
// ScriptableObject で BAD/GOOD ED 分岐の閾値を hot-fix 可能化。
// 仮値は Phase 8 で 5 名内部キャリブレーションして調整する。
//
// 関連 spec: SS-002, SS-003

using UnityEngine;

namespace VoiceHorror.KnnVc
{
    [CreateAssetMenu(
        fileName = "EdThresholdsAsset",
        menuName = "VoiceHorror/ED Thresholds",
        order = 100)]
    public class EdThresholdsAsset : ScriptableObject
    {
        [Tooltip("> HighThreshold で BadCaptured (カラダを奪われる)")]
        [Range(0f, 1f)]
        public float HighThreshold = 0.85f;

        [Tooltip("MidLow 〜 MidHigh で BadVoiceChange (声色変えて電話切れ)")]
        [Range(0f, 1f)]
        public float MidLow = 0.40f;

        [Range(0f, 1f)]
        public float MidHigh = 0.70f;
    }
}
