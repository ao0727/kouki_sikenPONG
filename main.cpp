/*エンターでスタート　Eで終了
WとSで上下移動
5本先取
*/


#include "DxLib.h"
#include "Title.h"
#include "Game.h"
#include "Menu.h"
#include "GameState.h"

#include <cstdlib>
#include <ctime>


int main() {
    srand(static_cast<unsigned>(time(0))); //乱数
}


int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    ChangeWindowMode(TRUE);
    if (DxLib_Init() == -1) return -1;
    SetDrawScreen(DX_SCREEN_BACK);

    GameState state = TITLE;
    Title title;
    Game game;
    Menu menu;

    while (ScreenFlip() == 0 && ProcessMessage() == 0 && ClearDrawScreen() == 0) {
        if (CheckHitKey(KEY_INPUT_E)) break; // Eキーで終了

        switch (state) {
        case TITLE:
            state = title.Update();
            break;
        case PLAYING:
            state = game.Update();
            break;
        case MENU:
            state = menu.Update();
            break;
        case GAME_OVER:
            state = TITLE;
            break;
        }
    }

    DxLib_End();
    return 0; // 正常終了
}
