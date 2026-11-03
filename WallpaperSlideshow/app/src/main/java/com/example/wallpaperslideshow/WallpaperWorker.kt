package com.example.wallpaperslideshow

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

/** WorkManager から定期的に呼ばれ、壁紙を次の画像に切り替える */
class WallpaperWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return when (WallpaperChanger(applicationContext).changeToNext()) {
            WallpaperChanger.Result.CHANGED -> Result.success()
            WallpaperChanger.Result.NO_IMAGES -> {
                // 画像が無くなったらスライドショーを止める
                SlideshowScheduler.stop(applicationContext)
                Result.success()
            }
            // 定期実行は失敗しても次の周期で再実行される
            WallpaperChanger.Result.FAILED -> Result.failure()
        }
    }
}
