package com.example.wallpaperslideshow

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

/**
 * スライドショーの設定と状態を保存する。
 * 画像はアプリ内部ストレージにコピーしたファイル名(順番付き)で管理する。
 */
class SlideshowPrefs(context: Context) {

    val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    /** 画像ファイル名の一覧(表示・切り替え順) */
    var images: List<String>
        get() = prefs.getString(KEY_IMAGES, null).toNameList()
        set(value) = prefs.edit { putString(KEY_IMAGES, value.joinToString(SEPARATOR)) }

    /** 切り替え間隔(分) */
    var intervalMinutes: Long
        get() = prefs.getLong(KEY_INTERVAL, DEFAULT_INTERVAL_MINUTES)
        set(value) = prefs.edit { putLong(KEY_INTERVAL, value) }

    var isRunning: Boolean
        get() = prefs.getBoolean(KEY_RUNNING, false)
        set(value) = prefs.edit { putBoolean(KEY_RUNNING, value) }

    var shuffle: Boolean
        get() = prefs.getBoolean(KEY_SHUFFLE, false)
        set(value) = prefs.edit {
            putBoolean(KEY_SHUFFLE, value)
            remove(KEY_SHUFFLE_QUEUE)
        }

    var applyToLockScreen: Boolean
        get() = prefs.getBoolean(KEY_APPLY_LOCK, false)
        set(value) = prefs.edit { putBoolean(KEY_APPLY_LOCK, value) }

    /** 現在壁紙に設定している画像のファイル名 */
    var currentImage: String?
        get() = prefs.getString(KEY_CURRENT, null)
        set(value) = prefs.edit { putString(KEY_CURRENT, value) }

    /** シャッフル時に「まだ表示していない画像」の残り */
    var shuffleQueue: List<String>
        get() = prefs.getString(KEY_SHUFFLE_QUEUE, null).toNameList()
        set(value) = prefs.edit { putString(KEY_SHUFFLE_QUEUE, value.joinToString(SEPARATOR)) }

    /** 最後に壁紙を切り替えた時刻(ミリ秒)。未実行なら0 */
    var lastChangedAt: Long
        get() = prefs.getLong(KEY_LAST_CHANGED, 0L)
        set(value) = prefs.edit { putLong(KEY_LAST_CHANGED, value) }

    private fun String?.toNameList(): List<String> =
        this?.split(SEPARATOR)?.filter { it.isNotBlank() } ?: emptyList()

    companion object {
        private const val NAME = "slideshow"
        private const val SEPARATOR = "\n"

        const val KEY_IMAGES = "images"
        const val KEY_INTERVAL = "interval_minutes"
        const val KEY_RUNNING = "running"
        const val KEY_SHUFFLE = "shuffle"
        const val KEY_APPLY_LOCK = "apply_lock"
        const val KEY_CURRENT = "current_image"
        const val KEY_SHUFFLE_QUEUE = "shuffle_queue"
        const val KEY_LAST_CHANGED = "last_changed_at"

        const val DEFAULT_INTERVAL_MINUTES = 60L
    }
}
