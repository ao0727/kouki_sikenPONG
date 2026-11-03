package com.example.wallpaperslideshow

/**
 * 選択できる切り替え間隔。
 * WorkManager の定期実行は最短15分のため、15分以上のみ用意している。
 */
enum class IntervalOption(val minutes: Long, val label: String) {
    MIN_15(15, "15分"),
    MIN_30(30, "30分"),
    HOUR_1(60, "1時間"),
    HOUR_2(120, "2時間"),
    HOUR_3(180, "3時間"),
    HOUR_6(360, "6時間"),
    HOUR_12(720, "12時間"),
    DAY_1(1440, "1日");

    companion object {
        fun fromMinutes(minutes: Long): IntervalOption =
            entries.firstOrNull { it.minutes == minutes } ?: HOUR_1
    }
}
