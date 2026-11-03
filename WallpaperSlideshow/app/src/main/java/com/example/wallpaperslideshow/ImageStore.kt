package com.example.wallpaperslideshow

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

/**
 * 選択された画像をアプリ内部ストレージにコピーして保持する。
 * (ギャラリー側のURI権限が切れても、バックグラウンドで確実に読めるようにするため)
 */
class ImageStore(context: Context) {

    private val appContext = context.applicationContext
    private val dir: File = File(appContext.filesDir, "slideshow").apply { mkdirs() }

    fun fileOf(name: String): File = File(dir, name)

    /** URI群をコピーし、作成したファイル名の一覧を返す(失敗したものは除外) */
    suspend fun import(uris: List<Uri>): List<String> = withContext(Dispatchers.IO) {
        uris.mapNotNull { uri ->
            val name = "${UUID.randomUUID()}.img"
            val file = File(dir, name)
            try {
                appContext.contentResolver.openInputStream(uri)?.use { input ->
                    file.outputStream().use { output -> input.copyTo(output) }
                } ?: return@mapNotNull null
                name
            } catch (e: Exception) {
                file.delete()
                null
            }
        }
    }

    suspend fun delete(names: Collection<String>) = withContext(Dispatchers.IO) {
        names.forEach { File(dir, it).delete() }
    }

    /** 一覧に含まれていない不要なファイルを掃除する */
    suspend fun deleteOrphans(keep: Collection<String>) = withContext(Dispatchers.IO) {
        val keepSet = keep.toSet()
        dir.listFiles()?.filter { it.name !in keepSet }?.forEach { it.delete() }
    }
}
