package com.midas.client.ui.components

import android.text.method.LinkMovementMethod
import android.text.util.Linkify
import android.widget.TextView
import androidx.core.text.util.LinkifyCompat
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import io.noties.markwon.Markwon

@Composable
fun MarkdownText(
    markdown: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val markwon = remember(context) { Markwon.create(context) }

    AndroidView(
        modifier = modifier,
        factory = { viewContext ->
            TextView(viewContext).apply {
                setTextIsSelectable(false)
                linksClickable = true
                movementMethod = LinkMovementMethod.getInstance()
            }
        },
        update = { view ->
            markwon.setMarkdown(view, markdown)
            LinkifyCompat.addLinks(view, Linkify.WEB_URLS)
        },
    )
}
