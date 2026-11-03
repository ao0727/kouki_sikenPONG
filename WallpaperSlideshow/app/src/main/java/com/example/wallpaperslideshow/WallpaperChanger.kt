package com.example.wallpaperslideshow

import android.app.WallpaperManager
import android.content.Context
import android.hardware.display.DisplayManager
import android.util.DisplayMetrics
import android.util.Log
import android.view.Display
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * 次の画像を選んで壁紙に設定する処理本体。
 */
class WallpaperChanger(context: Context) {

    private val appContext = context.applicationContext
    private val prefs = SlideshowPrefs(appContext)
    private val store = ImageStore(appContext)

    enum class Result { CHANGED, NO_IMAGES, FAILED }

    suspend fun changeToNext(): Result = mutex.withLock {
        withContext(Dispatchers.IO) { changeToNextLocked() }
    }

    private fun changeToNextLocked(): Result {
        // 存在しないファイルは一覧から除外しておく
        val all = prefs.images
        val images = all.filter { store.fileOf(it).exists() }
        if (images.size != all.size) prefs.images = images
        if (images.isEmpty()) return Result.NO_IMAGES

        val wallpaperManager = WallpaperManager.getInstance(appContext)
        if (!wallpaperManager.isWallpaperSupported || !wallpaperManager.isSetWallpaperAllowed) {
            Log.w(TAG, "この端末では壁紙を変更できません")
            return Result.FAILED
        }

        // 読めない画像があっても次の候補で試す
        var current = prefs.currentImage
        repeat(images.size) {
            val candidate = pickNext(images, current)
            try {
                apply(wallpaperManager, candidate)
                prefs.currentImage = candidate
                prefs.lastChangedAt = System.currentTimeMillis()
                return Result.CHANGED
            } catch (e: Exception) {
                Log.e(TAG, "壁紙の設定に失敗: $candidate", e)
                current = candidate
            }
        }
        return Result.FAILED
    }

    /** 次に表示する画像を決める */
    private fun pickNext(images: List<String>, current: String?): String {
        if (images.size == 1) return images[0]

        if (!prefs.shuffle) {
            val index = images.indexOf(current)
            return images[(index + 1) % images.size] // 見つからない場合(-1)は先頭
        }

        // シャッフル:全画像を1周するまで同じ画像を出さない
        var queue = prefs.shuffleQueue.filter { it in images }
        if (queue.isEmpty()) {
            queue = images.shuffled()
            // 周回の切れ目で同じ画像が2回続かないようにする
            if (queue.first() == current) queue = queue.drop(1) + queue.first()
        }
        prefs.shuffleQueue = queue.drop(1)
        return queue.first()
    }

    private fun apply(wallpaperManager: WallpaperManager, name: String) {
        val (width, height) = screenSize()
        val bitmap = BitmapLoader.loadCenterCrop(store.fileOf(name), width, height)
        try {
            val flags = if (prefs.applyToLockScreen) {
                WallpaperManager.FLAG_SYSTEM or WallpaperManager.FLAG_LOCK
            } else {
                WallpaperManager.FLAG_SYSTEM
            }
            wallpaperManager.setBitmap(bitmap, null, true, flags)
        } finally {
            bitmap.recycle()
        }
    }

    /** 画面の実サイズ(縦向き基準) */
    private fun screenSize(): Pair<Int, Int> {
        val displayManager = appContext.getSystemService(DisplayManager::class.java)
        val display = displayManager.getDisplay(Display.DEFAULT_DISPLAY)
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        display.getRealMetrics(metrics)
        val w = minOf(metrics.widthPixels, metrics.heightPixels)
        val h = maxOf(metrics.widthPixels, metrics.heightPixels)
        return w to h
    }

    companion object {
        private const val TAG = "WallpaperChanger"

        /** 定期実行と「今すぐ次へ」が同時に走らないようにする */
        private val mutex = Mutex()
    }
}
