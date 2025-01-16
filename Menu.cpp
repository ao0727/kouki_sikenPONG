#include "Menu.h"

int cursor = 0;

GameState Menu::Update() {
    const char* options[] = { "Resume", "Restart", "Quit to Title" };
    int optionCount = 3;

    // カーソル移動
    if (CheckHitKey(KEY_INPUT_W)) cursor = (cursor + optionCount - 1) % optionCount;
    if (CheckHitKey(KEY_INPUT_S)) cursor = (cursor + 1) % optionCount;

    // メニュー表示
    for (int i = 0; i < optionCount; i++) {
        int color = (i == cursor) ? GetColor(255, 0, 0) : GetColor(255, 255, 255);
        DrawString(200, 200 + i * 40, options[i], color);
    }

    // 選択処理
    if (CheckHitKey(KEY_INPUT_RETURN)) {
        if (cursor == 0) return PLAYING;   
        if (cursor == 1) return PLAYING;   // Restart
        if (cursor == 2) return TITLE;     
    }

    return MENU;
}
