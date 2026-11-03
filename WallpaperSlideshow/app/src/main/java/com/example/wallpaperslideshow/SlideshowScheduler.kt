package com.example.wallpaperslideshow

import android.content.Context
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * WorkManager でのスライドショーの予約・停止。
 * WorkManager は端末再起動後も自動で予約を復元してくれる。
 */
object SlideshowScheduler {

    const val PERIODIC_WORK = "wallpaper_slideshow_periodic"
    private const val ONE_TIME_WORK = "wallpaper_slideshow_now"

    /** 開始:すぐに1枚目を設定し、以後は間隔ごとに切り替える */
    fun start(context: Context) {
        SlideshowPrefs(context).isRunning = true
        changeNow(context)
        schedulePeriodic(context)
    }

    /** 実行中に間隔が変更されたときの再予約(すぐには切り替えない) */
    fun reschedule(context: Context) {
        if (SlideshowPrefs(context).isRunning) schedulePeriodic(context)
    }

    fun stop(context: Context) {
        SlideshowPrefs(context).isRunning = false
        WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_WORK)
    }

    /** 今すぐ次の画像に切り替える */
    fun changeNow(context: Context) {
        val request = OneTimeWorkRequestBuilder<WallpaperWorker>().build()
        WorkManager.getInstance(context)
            .enqueueUniqueWork(ONE_TIME_WORK, ExistingWorkPolicy.REPLACE, request)
    }

    private fun schedulePeriodic(context: Context) {
        val minutes = SlideshowPrefs(context).intervalMinutes
        val request = PeriodicWorkRequestBuilder<WallpaperWorker>(minutes, TimeUnit.MINUTES)
            .setInitialDelay(minutes, TimeUnit.MINUTES)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.CANCEL_AND_REENQUEUE,
            request
        )
    }
}
